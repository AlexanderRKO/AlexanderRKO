// App State
const state = {
    currentWorkout: null,
    currentExerciseIndex: 0,
    currentSetIndex: 0,
    workoutStartTime: null,
    workoutTimerInterval: null,
    restTimerInterval: null,
    restTimeRemaining: 0,
    exerciseData: {},
    settings: {
        compoundRest: 90,
        isolationRest: 60,
        soundEnabled: true,
        vibrationEnabled: true,
        startWeight: 68,
        goalWeight: 75
    }
};

// Local Storage Keys
const STORAGE_KEYS = {
    WORKOUT_HISTORY: 'workout_history',
    WEIGHT_LOG: 'weight_log',
    SETTINGS: 'settings'
};

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    initNavigation();
    initWorkoutSelection();
    initRestTimer();
    initProgressTab();
    initHistoryTab();
    initSettingsTab();
    updateProgressStats();
    updateHistoryList();
    populateExerciseSelect();
});

// ==================== NAVIGATION ====================
function initNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;

            // Update active tab
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Show corresponding content
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`${tabId}-tab`).classList.add('active');

            // Refresh data if needed
            if (tabId === 'progress') {
                updateProgressStats();
                updateWeightChart();
            } else if (tabId === 'history') {
                updateHistoryList();
            }
        });
    });
}

// ==================== WORKOUT SELECTION ====================
function initWorkoutSelection() {
    const workoutCards = document.querySelectorAll('.workout-card');
    workoutCards.forEach(card => {
        card.addEventListener('click', () => {
            const workoutType = card.dataset.workout;
            startWorkout(workoutType);
        });
    });

    document.getElementById('backToSelection').addEventListener('click', () => {
        if (confirm('Are you sure you want to exit this workout? Progress will be lost.')) {
            endWorkout(false);
        }
    });

    document.getElementById('finishWorkout').addEventListener('click', () => {
        completeWorkout();
    });
}

function startWorkout(type) {
    state.currentWorkout = type;
    state.currentExerciseIndex = 0;
    state.currentSetIndex = 0;
    state.workoutStartTime = Date.now();
    state.exerciseData = {};

    // Initialize exercise data
    const workout = WORKOUTS[type];
    workout.exercises.forEach((exercise, index) => {
        state.exerciseData[index] = {
            exerciseId: exercise.id,
            exerciseName: exercise.name,
            sets: Array(exercise.sets).fill().map(() => ({
                weight: '',
                reps: '',
                completed: false
            }))
        };
    });

    // Update UI
    document.getElementById('workoutSelection').classList.add('hidden');
    document.getElementById('activeWorkout').classList.remove('hidden');
    document.getElementById('activeWorkoutTitle').textContent = `Workout ${type}: ${workout.name}`;

    // Start workout timer
    startWorkoutTimer();

    // Render exercises
    renderExercises();
}

function renderExercises() {
    const workout = WORKOUTS[state.currentWorkout];
    const container = document.getElementById('exerciseList');
    container.innerHTML = '';

    workout.exercises.forEach((exercise, exerciseIndex) => {
        const exerciseData = state.exerciseData[exerciseIndex];
        const isCompleted = exerciseData.sets.every(s => s.completed);
        const isActive = exerciseIndex === state.currentExerciseIndex;

        const card = document.createElement('div');
        card.className = `exercise-card ${isCompleted ? 'completed' : ''} ${isActive ? 'active' : ''}`;
        card.dataset.index = exerciseIndex;

        card.innerHTML = `
            <div class="exercise-header">
                <div class="exercise-info">
                    <h3>${exercise.name}</h3>
                    <div class="exercise-meta">${exercise.sets} sets x ${exercise.reps} reps • ${exercise.muscle}</div>
                </div>
                <div class="exercise-status">
                    ${isCompleted ? '✓' : exerciseIndex + 1}
                </div>
            </div>
            <div class="exercise-body">
                <div class="exercise-tips">
                    💡 ${exercise.tips}
                </div>
                <div class="sets-grid">
                    ${exerciseData.sets.map((set, setIndex) => `
                        <div class="set-row ${set.completed ? 'completed' : ''}" data-set="${setIndex}">
                            <div class="set-number">${setIndex + 1}</div>
                            <div class="set-inputs">
                                <div class="input-group">
                                    <label>Weight (kg)</label>
                                    <input type="number"
                                           class="weight-input"
                                           value="${set.weight}"
                                           placeholder="0"
                                           step="0.5"
                                           data-exercise="${exerciseIndex}"
                                           data-set="${setIndex}"
                                           ${set.completed ? 'disabled' : ''}>
                                </div>
                                <div class="input-group">
                                    <label>Reps</label>
                                    <input type="number"
                                           class="reps-input"
                                           value="${set.reps}"
                                           placeholder="${exercise.reps}"
                                           data-exercise="${exerciseIndex}"
                                           data-set="${setIndex}"
                                           ${set.completed ? 'disabled' : ''}>
                                </div>
                            </div>
                            <button class="set-complete-btn"
                                    data-exercise="${exerciseIndex}"
                                    data-set="${setIndex}"
                                    ${set.completed ? 'disabled' : ''}>
                                ${set.completed ? '✓' : '→'}
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        // Add click handler for header to expand/collapse
        card.querySelector('.exercise-header').addEventListener('click', () => {
            if (!card.classList.contains('active')) {
                document.querySelectorAll('.exercise-card').forEach(c => c.classList.remove('expanded'));
                card.classList.toggle('expanded');
            }
        });

        container.appendChild(card);
    });

    // Add event listeners for inputs and buttons
    container.querySelectorAll('.weight-input, .reps-input').forEach(input => {
        input.addEventListener('change', handleSetInput);
        input.addEventListener('focus', (e) => e.target.select());
    });

    container.querySelectorAll('.set-complete-btn').forEach(btn => {
        btn.addEventListener('click', handleSetComplete);
    });

    // Check if all exercises complete
    const allComplete = Object.values(state.exerciseData).every(ex =>
        ex.sets.every(s => s.completed)
    );

    const finishBtn = document.getElementById('finishWorkout');
    if (allComplete) {
        finishBtn.classList.remove('hidden');
    } else {
        finishBtn.classList.add('hidden');
    }
}

function handleSetInput(e) {
    const exerciseIndex = parseInt(e.target.dataset.exercise);
    const setIndex = parseInt(e.target.dataset.set);
    const value = e.target.value;

    if (e.target.classList.contains('weight-input')) {
        state.exerciseData[exerciseIndex].sets[setIndex].weight = value;
    } else {
        state.exerciseData[exerciseIndex].sets[setIndex].reps = value;
    }
}

function handleSetComplete(e) {
    const exerciseIndex = parseInt(e.target.dataset.exercise);
    const setIndex = parseInt(e.target.dataset.set);
    const setData = state.exerciseData[exerciseIndex].sets[setIndex];

    // Mark set as complete
    setData.completed = true;

    // Get exercise for rest time
    const exercise = WORKOUTS[state.currentWorkout].exercises[exerciseIndex];
    const restTime = exercise.type === 'compound' ?
        state.settings.compoundRest : state.settings.isolationRest;

    // Determine next exercise preview
    let nextPreview = '';
    const isLastSet = setIndex === state.exerciseData[exerciseIndex].sets.length - 1;

    if (isLastSet) {
        // Check if there's a next exercise
        if (exerciseIndex < WORKOUTS[state.currentWorkout].exercises.length - 1) {
            const nextExercise = WORKOUTS[state.currentWorkout].exercises[exerciseIndex + 1];
            nextPreview = `Next: ${nextExercise.name}`;
            state.currentExerciseIndex = exerciseIndex + 1;
        } else {
            nextPreview = 'Final set! Great work!';
        }
    } else {
        nextPreview = `Set ${setIndex + 2} of ${exercise.name}`;
    }

    // Re-render exercises
    renderExercises();

    // Start rest timer (unless it's the final set of the workout)
    const allComplete = Object.values(state.exerciseData).every(ex =>
        ex.sets.every(s => s.completed)
    );

    if (!allComplete) {
        startRestTimer(restTime, nextPreview);
    }
}

function startWorkoutTimer() {
    const timerDisplay = document.getElementById('workoutTimer');

    state.workoutTimerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - state.workoutStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        timerDisplay.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }, 1000);
}

function endWorkout(save = false) {
    // Clear timers
    if (state.workoutTimerInterval) {
        clearInterval(state.workoutTimerInterval);
        state.workoutTimerInterval = null;
    }

    // Reset UI
    document.getElementById('workoutSelection').classList.remove('hidden');
    document.getElementById('activeWorkout').classList.add('hidden');
    document.getElementById('workoutTimer').textContent = '00:00';
    document.getElementById('finishWorkout').classList.add('hidden');

    // Reset state
    state.currentWorkout = null;
    state.exerciseData = {};
}

function completeWorkout() {
    const duration = Math.floor((Date.now() - state.workoutStartTime) / 1000);

    // Build workout record
    const workoutRecord = {
        id: Date.now(),
        date: new Date().toISOString(),
        type: state.currentWorkout,
        workoutName: WORKOUTS[state.currentWorkout].name,
        duration: duration,
        exercises: Object.values(state.exerciseData).map(ex => ({
            exerciseId: ex.exerciseId,
            exerciseName: ex.exerciseName,
            sets: ex.sets.filter(s => s.completed).map(s => ({
                weight: parseFloat(s.weight) || 0,
                reps: parseInt(s.reps) || 0
            }))
        }))
    };

    // Save to history
    const history = JSON.parse(localStorage.getItem(STORAGE_KEYS.WORKOUT_HISTORY) || '[]');
    history.unshift(workoutRecord);
    localStorage.setItem(STORAGE_KEYS.WORKOUT_HISTORY, JSON.stringify(history));

    // Show completion message
    alert(`Workout Complete!\n\nDuration: ${Math.floor(duration / 60)} minutes\n\nGreat work! Keep pushing towards 75kg!`);

    // End workout
    endWorkout(true);
}

// ==================== REST TIMER ====================
function initRestTimer() {
    document.getElementById('skipRest').addEventListener('click', () => {
        stopRestTimer();
    });

    document.getElementById('addTime').addEventListener('click', () => {
        state.restTimeRemaining += 30;
        updateRestTimerDisplay();
    });
}

function startRestTimer(seconds, nextPreview) {
    state.restTimeRemaining = seconds;

    const overlay = document.getElementById('restTimerOverlay');
    const display = document.getElementById('restTimerDisplay');
    const preview = document.getElementById('nextExercisePreview');

    preview.textContent = nextPreview;
    overlay.classList.remove('hidden');
    updateRestTimerDisplay();

    state.restTimerInterval = setInterval(() => {
        state.restTimeRemaining--;
        updateRestTimerDisplay();

        if (state.restTimeRemaining <= 0) {
            stopRestTimer();
            playAlert();
        }
    }, 1000);
}

function updateRestTimerDisplay() {
    document.getElementById('restTimerDisplay').textContent = state.restTimeRemaining;
}

function stopRestTimer() {
    if (state.restTimerInterval) {
        clearInterval(state.restTimerInterval);
        state.restTimerInterval = null;
    }
    document.getElementById('restTimerOverlay').classList.add('hidden');
}

function playAlert() {
    // Vibration
    if (state.settings.vibrationEnabled && navigator.vibrate) {
        navigator.vibrate([200, 100, 200, 100, 200]);
    }

    // Sound
    if (state.settings.soundEnabled) {
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.frequency.value = 880;
            oscillator.type = 'sine';
            gainNode.gain.value = 0.3;

            oscillator.start();

            setTimeout(() => {
                oscillator.stop();
                audioContext.close();
            }, 500);
        } catch (e) {
            console.log('Audio not available');
        }
    }
}

// ==================== PROGRESS TAB ====================
function initProgressTab() {
    document.getElementById('logWeight').addEventListener('click', () => {
        const input = document.getElementById('weightInput');
        const weight = parseFloat(input.value);

        if (weight && weight > 0) {
            logWeight(weight);
            input.value = '';
            updateProgressStats();
            updateWeightChart();
        }
    });

    document.getElementById('exerciseSelect').addEventListener('change', (e) => {
        if (e.target.value) {
            updateStrengthChart(e.target.value);
        }
    });
}

function logWeight(weight) {
    const log = JSON.parse(localStorage.getItem(STORAGE_KEYS.WEIGHT_LOG) || '[]');
    log.push({
        date: new Date().toISOString(),
        weight: weight
    });
    localStorage.setItem(STORAGE_KEYS.WEIGHT_LOG, JSON.stringify(log));

    // Update header display
    document.getElementById('currentWeight').textContent = weight.toFixed(1);
}

function updateProgressStats() {
    const log = JSON.parse(localStorage.getItem(STORAGE_KEYS.WEIGHT_LOG) || '[]');
    const history = JSON.parse(localStorage.getItem(STORAGE_KEYS.WORKOUT_HISTORY) || '[]');

    // Weight stats
    const startWeight = state.settings.startWeight;
    const goalWeight = state.settings.goalWeight;
    const latestWeight = log.length > 0 ? log[log.length - 1].weight : startWeight;
    const gained = latestWeight - startWeight;
    const toGo = goalWeight - latestWeight;

    document.getElementById('startingWeight').textContent = startWeight.toFixed(1);
    document.getElementById('latestWeight').textContent = latestWeight.toFixed(1);
    document.getElementById('weightGained').textContent = gained >= 0 ? `+${gained.toFixed(1)}` : gained.toFixed(1);
    document.getElementById('weightToGo').textContent = toGo.toFixed(1);
    document.getElementById('currentWeight').textContent = latestWeight.toFixed(1);

    // Workout stats
    document.getElementById('totalWorkouts').textContent = history.length;

    // This week
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    const thisWeek = history.filter(w => new Date(w.date) > oneWeekAgo).length;
    document.getElementById('thisWeek').textContent = thisWeek;

    // Calculate streak (weeks with at least 2 workouts)
    let streak = 0;
    let checkDate = new Date();
    while (true) {
        const weekStart = new Date(checkDate);
        weekStart.setDate(weekStart.getDate() - weekStart.getDay());
        weekStart.setHours(0, 0, 0, 0);

        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 7);

        const workoutsInWeek = history.filter(w => {
            const d = new Date(w.date);
            return d >= weekStart && d < weekEnd;
        }).length;

        if (workoutsInWeek >= 2) {
            streak++;
            checkDate.setDate(checkDate.getDate() - 7);
        } else {
            break;
        }

        if (streak > 52) break; // Max 1 year
    }
    document.getElementById('currentStreak').textContent = streak;
}

function updateWeightChart() {
    const log = JSON.parse(localStorage.getItem(STORAGE_KEYS.WEIGHT_LOG) || '[]');
    const canvas = document.getElementById('weightChart');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (log.length < 2) {
        ctx.fillStyle = '#6b7280';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Log at least 2 weights to see chart', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Get last 30 entries or all
    const data = log.slice(-30);

    // Calculate min/max
    const weights = data.map(d => d.weight);
    const minWeight = Math.min(...weights, state.settings.startWeight) - 1;
    const maxWeight = Math.max(...weights, state.settings.goalWeight) + 1;

    // Drawing parameters
    const padding = { top: 20, right: 20, bottom: 30, left: 40 };
    const chartWidth = canvas.width - padding.left - padding.right;
    const chartHeight = canvas.height - padding.top - padding.bottom;

    // Draw goal line
    const goalY = padding.top + chartHeight - ((state.settings.goalWeight - minWeight) / (maxWeight - minWeight)) * chartHeight;
    ctx.strokeStyle = 'rgba(34, 197, 94, 0.5)';
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(padding.left, goalY);
    ctx.lineTo(canvas.width - padding.right, goalY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw line chart
    ctx.strokeStyle = '#4f46e5';
    ctx.lineWidth = 2;
    ctx.beginPath();

    data.forEach((entry, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        const y = padding.top + chartHeight - ((entry.weight - minWeight) / (maxWeight - minWeight)) * chartHeight;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();

    // Draw points
    data.forEach((entry, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        const y = padding.top + chartHeight - ((entry.weight - minWeight) / (maxWeight - minWeight)) * chartHeight;

        ctx.fillStyle = '#4f46e5';
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
    });

    // Draw Y axis labels
    ctx.fillStyle = '#6b7280';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`${maxWeight.toFixed(0)}kg`, padding.left - 5, padding.top + 10);
    ctx.fillText(`${minWeight.toFixed(0)}kg`, padding.left - 5, canvas.height - padding.bottom);
    ctx.fillText(`${state.settings.goalWeight}kg`, padding.left - 5, goalY + 4);
}

function populateExerciseSelect() {
    const select = document.getElementById('exerciseSelect');
    const exercises = getAllExercises();

    exercises.forEach(ex => {
        const option = document.createElement('option');
        option.value = ex.id;
        option.textContent = ex.name;
        select.appendChild(option);
    });
}

function updateStrengthChart(exerciseId) {
    const history = JSON.parse(localStorage.getItem(STORAGE_KEYS.WORKOUT_HISTORY) || '[]');
    const canvas = document.getElementById('strengthChart');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Get data for this exercise
    const data = [];
    history.forEach(workout => {
        const exercise = workout.exercises.find(e => e.exerciseId === exerciseId);
        if (exercise && exercise.sets.length > 0) {
            // Get max weight from this session
            const maxWeight = Math.max(...exercise.sets.map(s => s.weight));
            if (maxWeight > 0) {
                data.push({
                    date: workout.date,
                    weight: maxWeight
                });
            }
        }
    });

    data.reverse(); // Chronological order

    if (data.length < 2) {
        ctx.fillStyle = '#6b7280';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Not enough data for this exercise', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Calculate min/max
    const weights = data.map(d => d.weight);
    const minWeight = Math.min(...weights) - 2;
    const maxWeight = Math.max(...weights) + 2;

    // Drawing parameters
    const padding = { top: 20, right: 20, bottom: 30, left: 40 };
    const chartWidth = canvas.width - padding.left - padding.right;
    const chartHeight = canvas.height - padding.top - padding.bottom;

    // Draw line chart
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.beginPath();

    data.forEach((entry, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        const y = padding.top + chartHeight - ((entry.weight - minWeight) / (maxWeight - minWeight)) * chartHeight;

        if (i === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();

    // Draw points
    data.forEach((entry, i) => {
        const x = padding.left + (i / (data.length - 1)) * chartWidth;
        const y = padding.top + chartHeight - ((entry.weight - minWeight) / (maxWeight - minWeight)) * chartHeight;

        ctx.fillStyle = '#f59e0b';
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
    });

    // Draw Y axis labels
    ctx.fillStyle = '#6b7280';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`${maxWeight.toFixed(0)}kg`, padding.left - 5, padding.top + 10);
    ctx.fillText(`${minWeight.toFixed(0)}kg`, padding.left - 5, canvas.height - padding.bottom);
}

// ==================== HISTORY TAB ====================
function initHistoryTab() {
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            updateHistoryList(btn.dataset.filter);
        });
    });
}

function updateHistoryList(filter = 'all') {
    const history = JSON.parse(localStorage.getItem(STORAGE_KEYS.WORKOUT_HISTORY) || '[]');
    const container = document.getElementById('historyList');

    const filtered = filter === 'all' ? history : history.filter(w => w.type === filter);

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <p>No workouts yet. Start your first workout!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(workout => {
        const date = new Date(workout.date);
        const dateStr = date.toLocaleDateString('en-AU', {
            weekday: 'short',
            day: 'numeric',
            month: 'short'
        });
        const duration = Math.floor(workout.duration / 60);
        const totalSets = workout.exercises.reduce((sum, ex) => sum + ex.sets.length, 0);

        return `
            <div class="history-item" data-id="${workout.id}">
                <div class="history-item-header">
                    <div class="history-workout-type">
                        <div class="history-letter">${workout.type}</div>
                        <div class="history-name">${workout.workoutName}</div>
                    </div>
                    <div class="history-date">${dateStr}</div>
                </div>
                <div class="history-stats">
                    <span>⏱️ ${duration} min</span>
                    <span>💪 ${totalSets} sets</span>
                    <span class="history-item-detail">View details ▼</span>
                </div>
                <div class="history-exercises">
                    ${workout.exercises.map(ex => `
                        <div class="history-exercise">
                            <div class="history-exercise-name">${ex.exerciseName}</div>
                            <div class="history-exercise-sets">
                                ${ex.sets.map(s => `${s.weight}kg × ${s.reps}`).join(' | ')}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers for expansion
    container.querySelectorAll('.history-item').forEach(item => {
        item.querySelector('.history-item-detail').addEventListener('click', () => {
            item.classList.toggle('expanded');
        });
    });
}

// ==================== SETTINGS TAB ====================
function initSettingsTab() {
    // Load saved settings
    document.getElementById('compoundRest').value = state.settings.compoundRest;
    document.getElementById('isolationRest').value = state.settings.isolationRest;
    document.getElementById('soundEnabled').checked = state.settings.soundEnabled;
    document.getElementById('vibrationEnabled').checked = state.settings.vibrationEnabled;
    document.getElementById('settingStartWeight').value = state.settings.startWeight;
    document.getElementById('settingGoalWeight').value = state.settings.goalWeight;

    // Rest timer settings
    document.getElementById('compoundRest').addEventListener('change', (e) => {
        state.settings.compoundRest = parseInt(e.target.value);
        saveSettings();
    });

    document.getElementById('isolationRest').addEventListener('change', (e) => {
        state.settings.isolationRest = parseInt(e.target.value);
        saveSettings();
    });

    // Sound settings
    document.getElementById('soundEnabled').addEventListener('change', (e) => {
        state.settings.soundEnabled = e.target.checked;
        saveSettings();
    });

    document.getElementById('vibrationEnabled').addEventListener('change', (e) => {
        state.settings.vibrationEnabled = e.target.checked;
        saveSettings();
    });

    // Goals
    document.getElementById('saveGoals').addEventListener('click', () => {
        state.settings.startWeight = parseFloat(document.getElementById('settingStartWeight').value);
        state.settings.goalWeight = parseFloat(document.getElementById('settingGoalWeight').value);
        saveSettings();
        updateProgressStats();
        alert('Goals saved!');
    });

    // Data management
    document.getElementById('exportData').addEventListener('click', exportData);
    document.getElementById('importData').addEventListener('click', () => {
        document.getElementById('importFile').click();
    });
    document.getElementById('importFile').addEventListener('change', importData);
    document.getElementById('clearData').addEventListener('click', clearAllData);
}

function loadSettings() {
    const saved = localStorage.getItem(STORAGE_KEYS.SETTINGS);
    if (saved) {
        state.settings = { ...state.settings, ...JSON.parse(saved) };
    }
}

function saveSettings() {
    localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(state.settings));
}

function exportData() {
    const data = {
        settings: state.settings,
        workoutHistory: JSON.parse(localStorage.getItem(STORAGE_KEYS.WORKOUT_HISTORY) || '[]'),
        weightLog: JSON.parse(localStorage.getItem(STORAGE_KEYS.WEIGHT_LOG) || '[]'),
        exportDate: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `workout-data-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function importData(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        try {
            const data = JSON.parse(event.target.result);

            if (data.settings) {
                state.settings = data.settings;
                saveSettings();
            }

            if (data.workoutHistory) {
                localStorage.setItem(STORAGE_KEYS.WORKOUT_HISTORY, JSON.stringify(data.workoutHistory));
            }

            if (data.weightLog) {
                localStorage.setItem(STORAGE_KEYS.WEIGHT_LOG, JSON.stringify(data.weightLog));
            }

            alert('Data imported successfully!');
            location.reload();
        } catch (err) {
            alert('Error importing data. Please check the file format.');
        }
    };
    reader.readAsText(file);
}

function clearAllData() {
    if (confirm('Are you sure you want to delete ALL data? This cannot be undone.')) {
        if (confirm('Really? All your workout history and weight logs will be gone forever.')) {
            localStorage.removeItem(STORAGE_KEYS.WORKOUT_HISTORY);
            localStorage.removeItem(STORAGE_KEYS.WEIGHT_LOG);
            localStorage.removeItem(STORAGE_KEYS.SETTINGS);
            alert('All data cleared.');
            location.reload();
        }
    }
}
