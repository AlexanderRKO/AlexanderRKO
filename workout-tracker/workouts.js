// Workout definitions based on the training program
const WORKOUTS = {
    A: {
        name: "Push Focus",
        description: "Chest, Shoulders, Triceps, Quads",
        exercises: [
            {
                id: "smith-squat",
                name: "Smith Machine Squat",
                sets: 4,
                reps: "8-10",
                restSeconds: 90,
                type: "compound",
                muscle: "Quads, Glutes",
                tips: "Feet shoulder-width, descend until thighs parallel. Drive through heels."
            },
            {
                id: "smith-bench",
                name: "Smith Machine Bench Press",
                sets: 4,
                reps: "8-10",
                restSeconds: 90,
                type: "compound",
                muscle: "Chest, Triceps",
                tips: "Bar to mid-chest, keep shoulder blades pinched. Press explosively."
            },
            {
                id: "cable-fly",
                name: "Cable Chest Fly",
                sets: 3,
                reps: "12",
                restSeconds: 60,
                type: "isolation",
                muscle: "Chest",
                tips: "Pulleys at shoulder height, slight elbow bend. Squeeze at center."
            },
            {
                id: "db-shoulder-press",
                name: "Dumbbell Shoulder Press",
                sets: 3,
                reps: "10-12",
                restSeconds: 60,
                type: "compound",
                muscle: "Shoulders",
                tips: "Press straight up, control the descent. Don't flare elbows."
            },
            {
                id: "tricep-pushdown",
                name: "Tricep Rope Pushdown",
                sets: 3,
                reps: "12-15",
                restSeconds: 60,
                type: "isolation",
                muscle: "Triceps",
                tips: "Keep elbows pinned to sides. Pull rope apart at bottom."
            },
            {
                id: "goblet-squat",
                name: "Kettlebell Goblet Squat",
                sets: 3,
                reps: "12",
                restSeconds: 60,
                type: "compound",
                muscle: "Quads, Core",
                tips: "Hold kettlebell at chest, deep squat, elbows inside knees."
            }
        ]
    },
    B: {
        name: "Pull Focus",
        description: "Back, Biceps, Hamstrings, Glutes",
        exercises: [
            {
                id: "smith-rdl",
                name: "Smith Machine Romanian Deadlift",
                sets: 4,
                reps: "8-10",
                restSeconds: 90,
                type: "compound",
                muscle: "Hamstrings, Glutes",
                tips: "Slight knee bend, hinge at hips. Feel hamstring stretch, squeeze glutes at top."
            },
            {
                id: "pullups",
                name: "Pull-Ups",
                sets: 4,
                reps: "6-10",
                restSeconds: 90,
                type: "compound",
                muscle: "Lats, Biceps",
                tips: "Full extension at bottom, chin over bar at top. Use band if needed."
            },
            {
                id: "cable-row",
                name: "Cable Row (Close Grip)",
                sets: 4,
                reps: "10-12",
                restSeconds: 60,
                type: "compound",
                muscle: "Mid Back, Lats",
                tips: "Sit tall, pull to lower chest. Squeeze shoulder blades together."
            },
            {
                id: "db-row",
                name: "Dumbbell Bent Over Row",
                sets: 3,
                reps: "10 each",
                restSeconds: 60,
                type: "compound",
                muscle: "Lats, Rhomboids",
                tips: "Support on bench, pull elbow back, squeeze at top."
            },
            {
                id: "cable-curl",
                name: "Cable Bicep Curl",
                sets: 3,
                reps: "12-15",
                restSeconds: 60,
                type: "isolation",
                muscle: "Biceps",
                tips: "Keep elbows stationary. Full range of motion, slow negative."
            },
            {
                id: "face-pulls",
                name: "Face Pulls",
                sets: 3,
                reps: "15",
                restSeconds: 60,
                type: "isolation",
                muscle: "Rear Delts",
                tips: "High pulley, pull to face, externally rotate at end."
            }
        ]
    },
    C: {
        name: "Full Body Power",
        description: "All Major Muscle Groups",
        exercises: [
            {
                id: "smith-front-squat",
                name: "Smith Machine Front Squat",
                sets: 3,
                reps: "8",
                restSeconds: 90,
                type: "compound",
                muscle: "Quads, Core",
                tips: "Bar on front delts, elbows high. Keep torso upright."
            },
            {
                id: "close-grip-bench",
                name: "Smith Machine Close Grip Bench",
                sets: 3,
                reps: "10",
                restSeconds: 90,
                type: "compound",
                muscle: "Triceps, Chest",
                tips: "Hands shoulder-width, elbows close to body. Focus on triceps."
            },
            {
                id: "tbar-row",
                name: "T-Bar Row",
                sets: 4,
                reps: "10",
                restSeconds: 60,
                type: "compound",
                muscle: "Back, Lats",
                tips: "Hinge at hips, pull to chest, squeeze back at top."
            },
            {
                id: "cable-lateral",
                name: "Cable Lateral Raises",
                sets: 3,
                reps: "12-15",
                restSeconds: 60,
                type: "isolation",
                muscle: "Side Delts",
                tips: "Single arm, slight lean away. Raise to shoulder height."
            },
            {
                id: "db-lunges",
                name: "Dumbbell Lunges",
                sets: 3,
                reps: "10 each",
                restSeconds: 60,
                type: "compound",
                muscle: "Quads, Glutes",
                tips: "Step forward, lower back knee to ground. Drive through front heel."
            },
            {
                id: "hanging-leg-raise",
                name: "Hanging Leg Raises",
                sets: 3,
                reps: "10-15",
                restSeconds: 60,
                type: "isolation",
                muscle: "Abs, Core",
                tips: "Hang from bar, raise legs to 90 degrees. Control the descent."
            }
        ]
    }
};

// Get all unique exercise IDs for progress tracking
function getAllExercises() {
    const exercises = [];
    Object.values(WORKOUTS).forEach(workout => {
        workout.exercises.forEach(ex => {
            if (!exercises.find(e => e.id === ex.id)) {
                exercises.push({ id: ex.id, name: ex.name });
            }
        });
    });
    return exercises;
}
