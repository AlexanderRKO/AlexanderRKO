"""
Xero API Client.

Provides a high-level client for interacting with the Xero Accounting API.
Handles automatic token refresh, rate limiting, and retry logic.

Features:
- Automatic access token refresh when expired
- Rate limiting to respect Xero API limits (60 calls/minute)
- Exponential backoff for transient failures
- Multi-tenant support with tenant ID headers
- Comprehensive error handling
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional, Union
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .xero_config import (
    XeroConfig,
    load_config,
    XERO_ACCOUNTING_API,
    XERO_ASSETS_API,
    XERO_PROJECTS_API,
)
from .xero_oauth import XeroOAuth, XeroTokens, TokenError
from .xero_tokens import TokenStorage

logger = logging.getLogger(__name__)


class XeroAPIError(Exception):
    """Raised when Xero API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: int = None,
        error_code: str = None,
        response_body: str = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body


class RateLimitError(XeroAPIError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class InvoiceStatus(Enum):
    """Xero invoice statuses."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTHORISED = "AUTHORISED"
    PAID = "PAID"
    VOIDED = "VOIDED"
    DELETED = "DELETED"


class ContactStatus(Enum):
    """Xero contact statuses."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    GDPRREQUEST = "GDPRREQUEST"


@dataclass
class XeroContact:
    """Xero contact representation."""

    contact_id: str
    name: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    account_number: Optional[str] = None
    tax_number: Optional[str] = None
    status: str = "ACTIVE"
    is_supplier: bool = False
    is_customer: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> "XeroContact":
        """Create from API response dictionary."""
        return cls(
            contact_id=data.get("ContactID", ""),
            name=data.get("Name", ""),
            email=data.get("EmailAddress"),
            first_name=data.get("FirstName"),
            last_name=data.get("LastName"),
            account_number=data.get("AccountNumber"),
            tax_number=data.get("TaxNumber"),
            status=data.get("ContactStatus", "ACTIVE"),
            is_supplier=data.get("IsSupplier", False),
            is_customer=data.get("IsCustomer", False),
        )


@dataclass
class XeroInvoice:
    """Xero invoice representation."""

    invoice_id: str
    invoice_number: str
    type: str
    status: str
    contact_name: str
    date: Optional[date] = None
    due_date: Optional[date] = None
    total: Decimal = Decimal("0")
    amount_due: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    currency_code: str = "AUD"

    @classmethod
    def from_dict(cls, data: Dict) -> "XeroInvoice":
        """Create from API response dictionary."""
        # Parse dates
        date_str = data.get("Date", "")
        due_date_str = data.get("DueDate", "")

        invoice_date = None
        due_date = None

        if date_str:
            # Xero uses /Date(timestamp)/ format
            if "/Date(" in date_str:
                timestamp = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                invoice_date = datetime.fromtimestamp(timestamp / 1000).date()

        if due_date_str:
            if "/Date(" in due_date_str:
                timestamp = int(due_date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                due_date = datetime.fromtimestamp(timestamp / 1000).date()

        return cls(
            invoice_id=data.get("InvoiceID", ""),
            invoice_number=data.get("InvoiceNumber", ""),
            type=data.get("Type", ""),
            status=data.get("Status", ""),
            contact_name=data.get("Contact", {}).get("Name", ""),
            date=invoice_date,
            due_date=due_date,
            total=Decimal(str(data.get("Total", 0))),
            amount_due=Decimal(str(data.get("AmountDue", 0))),
            amount_paid=Decimal(str(data.get("AmountPaid", 0))),
            currency_code=data.get("CurrencyCode", "AUD"),
        )


@dataclass
class XeroAccount:
    """Xero account (chart of accounts) representation."""

    account_id: str
    code: str
    name: str
    type: str
    status: str = "ACTIVE"
    tax_type: Optional[str] = None
    description: Optional[str] = None
    enable_payments: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> "XeroAccount":
        """Create from API response dictionary."""
        return cls(
            account_id=data.get("AccountID", ""),
            code=data.get("Code", ""),
            name=data.get("Name", ""),
            type=data.get("Type", ""),
            status=data.get("Status", "ACTIVE"),
            tax_type=data.get("TaxType"),
            description=data.get("Description"),
            enable_payments=data.get("EnablePaymentsToAccount", False),
        )


@dataclass
class XeroOrganisation:
    """Xero organisation details."""

    organisation_id: str
    name: str
    legal_name: Optional[str] = None
    short_code: Optional[str] = None
    country_code: str = "AU"
    default_currency: str = "AUD"
    organisation_type: Optional[str] = None
    is_demo_company: bool = False
    financial_year_end_day: int = 30
    financial_year_end_month: int = 6

    @classmethod
    def from_dict(cls, data: Dict) -> "XeroOrganisation":
        """Create from API response dictionary."""
        return cls(
            organisation_id=data.get("OrganisationID", ""),
            name=data.get("Name", ""),
            legal_name=data.get("LegalName"),
            short_code=data.get("ShortCode"),
            country_code=data.get("CountryCode", "AU"),
            default_currency=data.get("DefaultCurrency", "AUD"),
            organisation_type=data.get("OrganisationType"),
            is_demo_company=data.get("IsDemoCompany", False),
            financial_year_end_day=data.get("FinancialYearEndDay", 30),
            financial_year_end_month=data.get("FinancialYearEndMonth", 6),
        )


class XeroClient:
    """
    Xero API Client with automatic token management.

    Handles all API communication with Xero, including:
    - Automatic token refresh when expired
    - Rate limiting (60 calls/minute)
    - Exponential backoff for transient errors
    - Multi-tenant support

    Usage:
        # Initialize with stored tokens
        client = XeroClient()

        # Or with explicit tokens
        client = XeroClient(tokens=my_tokens, tenant_id="xxx")

        # Make API calls
        contacts = client.get_contacts()
        invoices = client.get_invoices(status="AUTHORISED")
        org = client.get_organisation()
    """

    def __init__(
        self,
        config: Optional[XeroConfig] = None,
        tokens: Optional[XeroTokens] = None,
        tenant_id: Optional[str] = None,
        token_storage: Optional[TokenStorage] = None,
        on_token_refresh: Optional[Callable[[XeroTokens], None]] = None,
    ):
        """
        Initialize Xero API client.

        Args:
            config: Xero configuration
            tokens: OAuth tokens (loaded from storage if not provided)
            tenant_id: Tenant ID to use (uses default if not provided)
            token_storage: Token storage instance
            on_token_refresh: Callback when tokens are refreshed
        """
        self.config = config or load_config()
        self._oauth = XeroOAuth(self.config)
        self._storage = token_storage
        self._on_token_refresh = on_token_refresh

        # Set up session with retry logic
        self._session = self._create_session()

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0

        # Set tokens and tenant
        self._tokens = tokens
        self._tenant_id = tenant_id

        # Load from storage if not provided
        if not self._tokens and self._storage:
            self._tenant_id = tenant_id or self._storage.get_default_tenant()
            if self._tenant_id:
                self._tokens = self._storage.get_tokens(self._tenant_id)

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update({
            "User-Agent": "PortfolioTracker/1.0",
            "Accept": "application/json",
        })

        return session

    def _rate_limit(self):
        """Apply rate limiting before making a request."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _ensure_tokens(self):
        """Ensure we have valid tokens, refreshing if needed."""
        if not self._tokens:
            raise XeroAPIError("No tokens available - please authenticate first")

        if self._tokens.is_expired:
            logger.info("Access token expired, refreshing...")
            try:
                new_tokens = self._oauth.refresh_tokens(self._tokens.refresh_token)
                self._tokens = new_tokens

                # Save to storage
                if self._storage and self._tenant_id:
                    self._storage.save_tokens(new_tokens, self._tenant_id)

                # Notify callback
                if self._on_token_refresh:
                    self._on_token_refresh(new_tokens)

                logger.info("Tokens refreshed successfully")

            except TokenError as e:
                raise XeroAPIError(f"Failed to refresh tokens: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request."""
        self._ensure_tokens()

        headers = {
            "Authorization": f"Bearer {self._tokens.access_token}",
            "Content-Type": "application/json",
        }

        if self._tenant_id:
            headers["Xero-tenant-id"] = self._tenant_id

        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        base_url: str = None,
        params: Dict = None,
        json_data: Dict = None,
    ) -> Dict:
        """
        Make an API request to Xero.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/Contacts")
            base_url: Base URL (defaults to Accounting API)
            params: Query parameters
            json_data: JSON body for POST/PUT requests

        Returns:
            Response JSON as dictionary

        Raises:
            XeroAPIError: If request fails
            RateLimitError: If rate limit exceeded
        """
        self._rate_limit()

        base_url = base_url or XERO_ACCOUNTING_API
        url = urljoin(base_url + "/", endpoint.lstrip("/"))

        headers = self._get_headers()

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=self.config.request_timeout,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    "Rate limit exceeded",
                    retry_after=retry_after,
                )

            # Handle errors
            if response.status_code >= 400:
                error_body = response.text
                try:
                    error_data = response.json()
                    error_message = error_data.get("Message", error_body)
                except:
                    error_message = error_body

                raise XeroAPIError(
                    f"API error: {error_message}",
                    status_code=response.status_code,
                    response_body=error_body,
                )

            # Return JSON response
            if response.text:
                return response.json()
            return {}

        except requests.RequestException as e:
            raise XeroAPIError(f"Network error: {e}")

    def _get(self, endpoint: str, params: Dict = None, **kwargs) -> Dict:
        """Make GET request."""
        return self._request("GET", endpoint, params=params, **kwargs)

    def _post(self, endpoint: str, data: Dict, **kwargs) -> Dict:
        """Make POST request."""
        return self._request("POST", endpoint, json_data=data, **kwargs)

    def _put(self, endpoint: str, data: Dict, **kwargs) -> Dict:
        """Make PUT request."""
        return self._request("PUT", endpoint, json_data=data, **kwargs)

    def _delete(self, endpoint: str, **kwargs) -> Dict:
        """Make DELETE request."""
        return self._request("DELETE", endpoint, **kwargs)

    # Organisation endpoints

    def get_organisation(self) -> XeroOrganisation:
        """
        Get organisation details.

        Returns:
            XeroOrganisation object
        """
        response = self._get("/Organisation")
        orgs = response.get("Organisations", [])
        if orgs:
            return XeroOrganisation.from_dict(orgs[0])
        raise XeroAPIError("No organisation found in response")

    # Contact endpoints

    def get_contacts(
        self,
        status: Optional[str] = None,
        where: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[XeroContact]:
        """
        Get contacts.

        Args:
            status: Filter by status (ACTIVE, ARCHIVED)
            where: OData filter expression
            order: Sort order (e.g., "Name ASC")
            page: Page number
            page_size: Results per page (max 100)

        Returns:
            List of XeroContact objects
        """
        params = {"page": page}

        if status:
            params["where"] = f'ContactStatus=="{status}"'
        elif where:
            params["where"] = where

        if order:
            params["order"] = order

        response = self._get("/Contacts", params=params)
        contacts = response.get("Contacts", [])

        return [XeroContact.from_dict(c) for c in contacts]

    def get_contact(self, contact_id: str) -> XeroContact:
        """
        Get a single contact by ID.

        Args:
            contact_id: Contact ID

        Returns:
            XeroContact object
        """
        response = self._get(f"/Contacts/{contact_id}")
        contacts = response.get("Contacts", [])
        if contacts:
            return XeroContact.from_dict(contacts[0])
        raise XeroAPIError(f"Contact not found: {contact_id}")

    def iter_contacts(
        self,
        status: Optional[str] = None,
        where: Optional[str] = None,
    ) -> Generator[XeroContact, None, None]:
        """
        Iterate through all contacts with automatic pagination.

        Args:
            status: Filter by status
            where: OData filter expression

        Yields:
            XeroContact objects
        """
        page = 1
        while True:
            contacts = self.get_contacts(status=status, where=where, page=page)
            if not contacts:
                break
            yield from contacts
            if len(contacts) < 100:
                break
            page += 1

    # Invoice endpoints

    def get_invoices(
        self,
        status: Optional[str] = None,
        invoice_type: Optional[str] = None,
        where: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
    ) -> List[XeroInvoice]:
        """
        Get invoices.

        Args:
            status: Filter by status (DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED)
            invoice_type: Filter by type (ACCREC, ACCPAY)
            where: OData filter expression
            order: Sort order
            page: Page number

        Returns:
            List of XeroInvoice objects
        """
        params = {"page": page}

        filters = []
        if status:
            filters.append(f'Status=="{status}"')
        if invoice_type:
            filters.append(f'Type=="{invoice_type}"')
        if where:
            filters.append(where)

        if filters:
            params["where"] = " AND ".join(filters)

        if order:
            params["order"] = order

        response = self._get("/Invoices", params=params)
        invoices = response.get("Invoices", [])

        return [XeroInvoice.from_dict(i) for i in invoices]

    def get_invoice(self, invoice_id: str) -> XeroInvoice:
        """
        Get a single invoice by ID.

        Args:
            invoice_id: Invoice ID

        Returns:
            XeroInvoice object
        """
        response = self._get(f"/Invoices/{invoice_id}")
        invoices = response.get("Invoices", [])
        if invoices:
            return XeroInvoice.from_dict(invoices[0])
        raise XeroAPIError(f"Invoice not found: {invoice_id}")

    def iter_invoices(
        self,
        status: Optional[str] = None,
        invoice_type: Optional[str] = None,
    ) -> Generator[XeroInvoice, None, None]:
        """
        Iterate through all invoices with automatic pagination.

        Args:
            status: Filter by status
            invoice_type: Filter by type

        Yields:
            XeroInvoice objects
        """
        page = 1
        while True:
            invoices = self.get_invoices(status=status, invoice_type=invoice_type, page=page)
            if not invoices:
                break
            yield from invoices
            if len(invoices) < 100:
                break
            page += 1

    # Account endpoints

    def get_accounts(
        self,
        account_type: Optional[str] = None,
        where: Optional[str] = None,
    ) -> List[XeroAccount]:
        """
        Get chart of accounts.

        Args:
            account_type: Filter by type (BANK, CURRENT, CURRLIAB, etc.)
            where: OData filter expression

        Returns:
            List of XeroAccount objects
        """
        params = {}

        if account_type:
            params["where"] = f'Type=="{account_type}"'
        elif where:
            params["where"] = where

        response = self._get("/Accounts", params=params)
        accounts = response.get("Accounts", [])

        return [XeroAccount.from_dict(a) for a in accounts]

    def get_account(self, account_id: str) -> XeroAccount:
        """
        Get a single account by ID.

        Args:
            account_id: Account ID

        Returns:
            XeroAccount object
        """
        response = self._get(f"/Accounts/{account_id}")
        accounts = response.get("Accounts", [])
        if accounts:
            return XeroAccount.from_dict(accounts[0])
        raise XeroAPIError(f"Account not found: {account_id}")

    # Report endpoints

    def get_profit_and_loss(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        periods: int = 1,
        timeframe: str = "MONTH",
    ) -> Dict:
        """
        Get Profit and Loss report.

        Args:
            from_date: Report start date
            to_date: Report end date
            periods: Number of periods
            timeframe: Period timeframe (MONTH, QUARTER, YEAR)

        Returns:
            Report data dictionary
        """
        params = {
            "periods": periods,
            "timeframe": timeframe,
        }

        if from_date:
            params["fromDate"] = from_date.isoformat()
        if to_date:
            params["toDate"] = to_date.isoformat()

        return self._get("/Reports/ProfitAndLoss", params=params)

    def get_balance_sheet(
        self,
        report_date: Optional[date] = None,
        periods: int = 1,
        timeframe: str = "MONTH",
    ) -> Dict:
        """
        Get Balance Sheet report.

        Args:
            report_date: Report date
            periods: Number of periods
            timeframe: Period timeframe

        Returns:
            Report data dictionary
        """
        params = {
            "periods": periods,
            "timeframe": timeframe,
        }

        if report_date:
            params["date"] = report_date.isoformat()

        return self._get("/Reports/BalanceSheet", params=params)

    def get_trial_balance(self, report_date: Optional[date] = None) -> Dict:
        """
        Get Trial Balance report.

        Args:
            report_date: Report date

        Returns:
            Report data dictionary
        """
        params = {}
        if report_date:
            params["date"] = report_date.isoformat()

        return self._get("/Reports/TrialBalance", params=params)

    def get_bank_summary(self, from_date: Optional[date] = None, to_date: Optional[date] = None) -> Dict:
        """
        Get Bank Summary report.

        Args:
            from_date: Report start date
            to_date: Report end date

        Returns:
            Report data dictionary
        """
        params = {}
        if from_date:
            params["fromDate"] = from_date.isoformat()
        if to_date:
            params["toDate"] = to_date.isoformat()

        return self._get("/Reports/BankSummary", params=params)

    # Bank transaction endpoints

    def get_bank_transactions(
        self,
        bank_account_id: Optional[str] = None,
        where: Optional[str] = None,
        order: Optional[str] = None,
        page: int = 1,
    ) -> List[Dict]:
        """
        Get bank transactions.

        Args:
            bank_account_id: Filter by bank account ID
            where: OData filter expression
            order: Sort order
            page: Page number

        Returns:
            List of bank transaction dictionaries
        """
        params = {"page": page}

        if bank_account_id:
            params["where"] = f'BankAccount.AccountID==Guid("{bank_account_id}")'
        elif where:
            params["where"] = where

        if order:
            params["order"] = order

        response = self._get("/BankTransactions", params=params)
        return response.get("BankTransactions", [])

    # Utility methods

    def test_connection(self) -> bool:
        """
        Test the API connection.

        Returns:
            True if connection is successful
        """
        try:
            self.get_organisation()
            return True
        except XeroAPIError:
            return False

    def get_status(self) -> Dict:
        """
        Get client status information.

        Returns:
            Dictionary with status details
        """
        return {
            "has_tokens": self._tokens is not None,
            "tokens_expired": self._tokens.is_expired if self._tokens else None,
            "tenant_id": self._tenant_id,
            "connected": self.test_connection() if self._tokens else False,
        }

    @property
    def tokens(self) -> Optional[XeroTokens]:
        """Get current tokens."""
        return self._tokens

    @property
    def tenant_id(self) -> Optional[str]:
        """Get current tenant ID."""
        return self._tenant_id

    def set_tenant(self, tenant_id: str):
        """
        Set the active tenant ID.

        Args:
            tenant_id: Tenant ID to use for requests
        """
        self._tenant_id = tenant_id

        # Load tokens for this tenant from storage
        if self._storage:
            self._tokens = self._storage.get_tokens(tenant_id)
