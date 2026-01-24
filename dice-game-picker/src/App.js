import React, { useState } from 'react';
import './App.css';

// 30+ child-friendly games organized by dice number (1-6)
const gameCategories = {
  1: {
    name: "Active Games",
    emoji: "🏃",
    color: "#FF6B6B",
    games: [
      { name: "Simon Says", description: "One person gives commands starting with 'Simon says'. Only follow commands that start with 'Simon says'!", icon: "👋" },
      { name: "Freeze Dance", description: "Dance when the music plays, freeze when it stops! Last one moving is out.", icon: "💃" },
      { name: "Red Light, Green Light", description: "Run on green light, freeze on red light. Don't get caught moving!", icon: "🚦" },
      { name: "Musical Chairs", description: "Walk around chairs while music plays. Sit when it stops - one chair removed each round!", icon: "🪑" },
      { name: "Tag", description: "One person is 'it' and tries to tag others. When tagged, you become 'it'!", icon: "🏷️" }
    ]
  },
  2: {
    name: "Creative Activities",
    emoji: "🎨",
    color: "#4ECDC4",
    games: [
      { name: "Drawing Competition", description: "Everyone draws the same thing - vote for the best one!", icon: "✏️" },
      { name: "Play-Doh Sculptures", description: "Create amazing sculptures with play-doh. Build animals, food, or anything you imagine!", icon: "🎭" },
      { name: "Paper Airplane Contest", description: "Make paper airplanes and see whose flies the farthest!", icon: "✈️" },
      { name: "Finger Painting", description: "Get messy and create art with your fingers and colorful paints!", icon: "🖐️" },
      { name: "Origami Fun", description: "Fold paper into cool shapes like boats, frogs, and butterflies!", icon: "🦢" }
    ]
  },
  3: {
    name: "Brain Games",
    emoji: "🧠",
    color: "#95E1D3",
    games: [
      { name: "I Spy", description: "One person says 'I spy something...' with a color or shape. Others guess what it is!", icon: "👁️" },
      { name: "20 Questions", description: "Think of something, others ask yes/no questions to guess it in 20 tries!", icon: "❓" },
      { name: "Memory Match", description: "Flip cards to find matching pairs. Remember where each card is!", icon: "🃏" },
      { name: "Word Association", description: "Say a word, next person says a related word quickly. Don't repeat!", icon: "💬" },
      { name: "Riddle Time", description: "Take turns telling riddles and guessing the answers!", icon: "🤔" }
    ]
  },
  4: {
    name: "Outdoor Adventures",
    emoji: "🌳",
    color: "#A8E6CF",
    games: [
      { name: "Hide and Seek", description: "One person counts, others hide. Find everyone before they reach base!", icon: "🙈" },
      { name: "Nature Scavenger Hunt", description: "Find items from nature: a pinecone, a feather, a smooth rock, and more!", icon: "🔍" },
      { name: "Hopscotch", description: "Draw squares with chalk, toss a stone, and hop through without stepping on lines!", icon: "🦘" },
      { name: "Bug Safari", description: "Explore outside and spot as many different insects as you can!", icon: "🐛" },
      { name: "Cloud Watching", description: "Lay on the grass and find shapes in the clouds. What animals do you see?", icon: "☁️" }
    ]
  },
  5: {
    name: "Team Games",
    emoji: "🤝",
    color: "#DDA0DD",
    games: [
      { name: "Charades", description: "Act out a word without speaking. Your team tries to guess what it is!", icon: "🎭" },
      { name: "Telephone", description: "Whisper a message down the line. See how funny it changes at the end!", icon: "📞" },
      { name: "Hot Potato", description: "Pass an object quickly while music plays. Don't be holding it when music stops!", icon: "🥔" },
      { name: "Duck Duck Goose", description: "Sit in a circle. One person taps heads saying 'duck' until they pick a 'goose' to chase them!", icon: "🦆" },
      { name: "Relay Race", description: "Split into teams and race while passing a baton. Teamwork wins!", icon: "🏁" }
    ]
  },
  6: {
    name: "Quiet Activities",
    emoji: "📚",
    color: "#FFB347",
    games: [
      { name: "Story Time", description: "Take turns adding sentences to create a silly story together!", icon: "📖" },
      { name: "Puzzle Time", description: "Work together to complete a jigsaw puzzle!", icon: "🧩" },
      { name: "Building Blocks", description: "Build the tallest tower or coolest creation with blocks or LEGO!", icon: "🧱" },
      { name: "Card Games", description: "Play Go Fish, Old Maid, or Crazy Eights!", icon: "🃏" },
      { name: "Coloring Party", description: "Everyone colors in a coloring book. Share your favorite colors!", icon: "🖍️" }
    ]
  }
};

// Dice face SVG component
function DiceFace({ value, isRolling }) {
  const dotPositions = {
    1: [[50, 50]],
    2: [[25, 25], [75, 75]],
    3: [[25, 25], [50, 50], [75, 75]],
    4: [[25, 25], [75, 25], [25, 75], [75, 75]],
    5: [[25, 25], [75, 25], [50, 50], [25, 75], [75, 75]],
    6: [[25, 25], [75, 25], [25, 50], [75, 50], [25, 75], [75, 75]]
  };

  return (
    <svg
      viewBox="0 0 100 100"
      className={`dice ${isRolling ? 'rolling' : ''}`}
      style={{ backgroundColor: gameCategories[value]?.color || '#fff' }}
    >
      <rect x="5" y="5" width="90" height="90" rx="10" ry="10" fill="white" stroke="#333" strokeWidth="2"/>
      {dotPositions[value]?.map((pos, i) => (
        <circle key={i} cx={pos[0]} cy={pos[1]} r="8" fill="#333" />
      ))}
    </svg>
  );
}

// Game Card component
function GameCard({ game, category }) {
  return (
    <div className="game-card" style={{ borderColor: category.color }}>
      <div className="game-icon">{game.icon}</div>
      <h3 className="game-name">{game.name}</h3>
      <p className="game-description">{game.description}</p>
      <div className="category-tag" style={{ backgroundColor: category.color }}>
        {category.emoji} {category.name}
      </div>
    </div>
  );
}

function App() {
  const [diceValue, setDiceValue] = useState(null);
  const [selectedGame, setSelectedGame] = useState(null);
  const [isRolling, setIsRolling] = useState(false);
  const [rollHistory, setRollHistory] = useState([]);

  const rollDice = () => {
    if (isRolling) return;

    setIsRolling(true);
    setSelectedGame(null);

    // Animate through random values
    let rolls = 0;
    const maxRolls = 15;
    const interval = setInterval(() => {
      setDiceValue(Math.floor(Math.random() * 6) + 1);
      rolls++;

      if (rolls >= maxRolls) {
        clearInterval(interval);
        const finalValue = Math.floor(Math.random() * 6) + 1;
        setDiceValue(finalValue);

        // Pick a random game from the category
        const category = gameCategories[finalValue];
        const randomGame = category.games[Math.floor(Math.random() * category.games.length)];

        setTimeout(() => {
          setSelectedGame({ game: randomGame, category });
          setRollHistory(prev => [...prev.slice(-4), { value: finalValue, game: randomGame.name }]);
          setIsRolling(false);
        }, 300);
      }
    }, 100);
  };

  const rerollSameCategory = () => {
    if (!diceValue || isRolling) return;

    const category = gameCategories[diceValue];
    const randomGame = category.games[Math.floor(Math.random() * category.games.length)];
    setSelectedGame({ game: randomGame, category });
    setRollHistory(prev => [...prev.slice(-4), { value: diceValue, game: randomGame.name }]);
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🎲 Dice Game Picker 🎮</h1>
        <p className="subtitle">Roll the dice to discover a fun game or activity!</p>
      </header>

      <main className="main-content">
        <div className="dice-section">
          <div className="dice-container" onClick={rollDice}>
            {diceValue ? (
              <DiceFace value={diceValue} isRolling={isRolling} />
            ) : (
              <div className="dice placeholder">
                <span>?</span>
              </div>
            )}
          </div>

          <button
            className="roll-button"
            onClick={rollDice}
            disabled={isRolling}
          >
            {isRolling ? '🎲 Rolling...' : '🎲 Roll the Dice!'}
          </button>

          {selectedGame && (
            <button
              className="reroll-button"
              onClick={rerollSameCategory}
              style={{ backgroundColor: selectedGame.category.color }}
            >
              🔄 Try another {selectedGame.category.name.toLowerCase()}
            </button>
          )}
        </div>

        {selectedGame && (
          <div className="result-section">
            <h2 className="result-title">Your Game Is...</h2>
            <GameCard game={selectedGame.game} category={selectedGame.category} />
          </div>
        )}

        {rollHistory.length > 0 && (
          <div className="history-section">
            <h3>Recent Rolls</h3>
            <div className="history-list">
              {rollHistory.map((roll, i) => (
                <div key={i} className="history-item" style={{ backgroundColor: gameCategories[roll.value].color }}>
                  <span className="history-dice">{roll.value}</span>
                  <span className="history-game">{roll.game}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="categories-section">
          <h2>All Game Categories</h2>
          <div className="categories-grid">
            {Object.entries(gameCategories).map(([num, cat]) => (
              <div key={num} className="category-card" style={{ borderColor: cat.color }}>
                <div className="category-header" style={{ backgroundColor: cat.color }}>
                  <span className="category-number">{num}</span>
                  <span className="category-emoji">{cat.emoji}</span>
                </div>
                <h3>{cat.name}</h3>
                <ul>
                  {cat.games.map((game, i) => (
                    <li key={i}>{game.icon} {game.name}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </main>

      <footer className="footer">
        <p>Made with ❤️ for fun family game time!</p>
      </footer>
    </div>
  );
}

export default App;
