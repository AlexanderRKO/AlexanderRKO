#!/bin/bash
# Schedule the NSW Auction Results scraper to run weekly
#
# Auction results are published every Sunday at 5am AEDT
# We schedule the scrape for 6am Sunday to ensure data is available
#
# Usage:
#   ./schedule_scraper.sh install   - Install the cron job
#   ./schedule_scraper.sh remove    - Remove the cron job
#   ./schedule_scraper.sh status    - Check if cron job is installed
#   ./schedule_scraper.sh run       - Run the scraper now

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Cron expression: 6am every Sunday (Sydney time - adjust for your timezone)
# Format: minute hour day-of-month month day-of-week
CRON_SCHEDULE="0 6 * * 0"
CRON_COMMENT="# NSW Auction Results Scraper - runs weekly on Sunday at 6am"

# Python executable - adjust if using a virtual environment
PYTHON_EXEC="${PYTHON_EXEC:-python3}"

# Full command to run
SCRAPE_COMMAND="cd $PROJECT_DIR && $PYTHON_EXEC src/runner.py scrape"

install_cron() {
    echo "Installing cron job..."

    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "NSW Auction Results Scraper"; then
        echo "Cron job already installed. Use 'remove' first to reinstall."
        return 1
    fi

    # Add cron job
    (crontab -l 2>/dev/null; echo "$CRON_COMMENT"; echo "$CRON_SCHEDULE $SCRAPE_COMMAND >> $PROJECT_DIR/logs/cron.log 2>&1") | crontab -

    if [ $? -eq 0 ]; then
        echo "Cron job installed successfully!"
        echo "Schedule: Every Sunday at 6:00 AM"
        echo "Command: $SCRAPE_COMMAND"
        echo ""
        echo "View logs at: $PROJECT_DIR/logs/cron.log"
    else
        echo "Failed to install cron job"
        return 1
    fi
}

remove_cron() {
    echo "Removing cron job..."

    # Remove lines containing our comment and the following line
    crontab -l 2>/dev/null | grep -v "NSW Auction Results Scraper" | crontab -

    echo "Cron job removed."
}

check_status() {
    echo "Checking cron job status..."

    if crontab -l 2>/dev/null | grep -q "NSW Auction Results Scraper"; then
        echo "Status: INSTALLED"
        echo ""
        echo "Current cron entry:"
        crontab -l 2>/dev/null | grep -A1 "NSW Auction Results Scraper"
    else
        echo "Status: NOT INSTALLED"
        echo ""
        echo "Run './schedule_scraper.sh install' to install."
    fi
}

run_now() {
    echo "Running scraper now..."
    cd "$PROJECT_DIR"
    $PYTHON_EXEC src/runner.py scrape
}

case "$1" in
    install)
        install_cron
        ;;
    remove)
        remove_cron
        ;;
    status)
        check_status
        ;;
    run)
        run_now
        ;;
    *)
        echo "NSW Auction Results Scraper - Scheduler"
        echo ""
        echo "Usage: $0 {install|remove|status|run}"
        echo ""
        echo "Commands:"
        echo "  install  - Install weekly cron job (Sundays at 6am)"
        echo "  remove   - Remove the cron job"
        echo "  status   - Check if cron job is installed"
        echo "  run      - Run the scraper immediately"
        ;;
esac
