import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import GameHistory from './GameHistory';

// API URL - adjust if needed
const API_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:12000/api' 
  : '/api';

// Socket URL
const SOCKET_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:12000' 
  : window.location.origin;

// Square component for each cell in the grid
const Square = ({ value, onClick, disabled, index }) => {
  return (
    <button 
      className="square" 
      onClick={onClick}
      disabled={disabled}
      data-value={value}
      data-index={index}
    >
      {value}
    </button>
  );
};

// Board component that renders the 3x3 grid
const Board = ({ squares, onClick, disabled }) => {
  return (
    <div className="board">
      {squares.map((value, index) => (
        <Square 
          key={index} 
          value={value} 
          onClick={() => onClick(index)}
          disabled={disabled || value !== null}
          index={index}
        />
      ))}
    </div>
  );
};

// Room Setup component for online multiplayer
const RoomSetup = ({ onCreateRoom, onJoinRoom, isLoading }) => {
  const [playerName, setPlayerName] = useState('');
  const [roomName, setRoomName] = useState('');
  const [roomCode, setRoomCode] = useState('');
  const [showJoinForm, setShowJoinForm] = useState(false);

  const handleCreateRoom = (e) => {
    e.preventDefault();
    if (!playerName.trim()) {
      alert('Please enter your name');
      return;
    }
    onCreateRoom({
      playerName: playerName.trim(),
      roomName: roomName.trim() || null
    });
  };

  const handleJoinRoom = (e) => {
    e.preventDefault();
    if (!playerName.trim()) {
      alert('Please enter your name');
      return;
    }
    if (!roomCode.trim()) {
      alert('Please enter a room code');
      return;
    }
    onJoinRoom({
      playerName: playerName.trim(),
      roomCode: roomCode.trim().toUpperCase()
    });
  };

  return (
    <div className="room-setup">
      <h3>Online Multiplayer</h3>
      
      <div className="player-name-input">
        <label>
          Your Name:
          <input
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            placeholder="Enter your name"
            maxLength={20}
            disabled={isLoading}
          />
        </label>
      </div>

      {!showJoinForm ? (
        <div className="room-options">
          <form onSubmit={handleCreateRoom} className="create-room-form">
            <label>
              Room Name (optional):
              <input
                type="text"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
                placeholder="My Awesome Game"
                maxLength={30}
                disabled={isLoading}
              />
            </label>
            <button type="submit" disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create Room'}
            </button>
          </form>
          
          <div className="or-divider">or</div>
          
          <button 
            onClick={() => setShowJoinForm(true)}
            className="join-room-button"
            disabled={isLoading}
          >
            Join Existing Room
          </button>
        </div>
      ) : (
        <div className="join-room-form">
          <form onSubmit={handleJoinRoom}>
            <label>
              Room Code:
              <input
                type="text"
                value={roomCode}
                onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                placeholder="BLUE42"
                maxLength={10}
                disabled={isLoading}
              />
            </label>
            <div className="form-buttons">
              <button type="submit" disabled={isLoading}>
                {isLoading ? 'Joining...' : 'Join Room'}
              </button>
              <button 
                type="button" 
                onClick={() => setShowJoinForm(false)}
                disabled={isLoading}
              >
                Back
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};

// Room Info component
const RoomInfo = ({ roomCode, roomName, players, currentPlayer, onLeaveRoom, onCopyRoomCode }) => {
  return (
    <div className="room-info">
      <div className="room-details">
        <h3>{roomName}</h3>
        <div className="room-code">
          Room Code: <strong>{roomCode}</strong>
          <button onClick={onCopyRoomCode} className="copy-button">
            Copy
          </button>
        </div>
      </div>
      
      <div className="players-info">
        <h4>Players ({players.length}/2):</h4>
        <ul>
          {players.map((player, index) => (
            <li key={player.id} className={player.id === currentPlayer?.id ? 'current-player' : ''}>
              {player.name} ({player.symbol})
              {player.id === currentPlayer?.id && ' (You)'}
            </li>
          ))}
        </ul>
        {players.length < 2 && (
          <p className="waiting-message">Waiting for another player to join...</p>
        )}
      </div>
      
      <button onClick={onLeaveRoom} className="leave-room-button">
        Leave Room
      </button>
    </div>
  );
};

// Score Tracker component
const ScoreTracker = ({ scores }) => {
  return (
    <div className="score-tracker">
      <div className="score-item">
        <div className="score-label">X Wins</div>
        <div className="score-value">{scores.X}</div>
      </div>
      <div className="score-item">
        <div className="score-label">Draws</div>
        <div className="score-value">{scores.draws}</div>
      </div>
      <div className="score-item">
        <div className="score-label">O Wins</div>
        <div className="score-value">{scores.O}</div>
      </div>
    </div>
  );
};

// Turn Indicator component
const TurnIndicator = ({ xIsNext, gameMode, currentPlayer }) => {
  if (gameMode === 'online' && currentPlayer) {
    return (
      <div className="turn-indicator">
        <div className={`player-badge ${currentPlayer.symbol === 'X' ? 'player-x' : 'player-o'} ${
          (xIsNext && currentPlayer.symbol === 'X') || (!xIsNext && currentPlayer.symbol === 'O') ? 'active' : ''
        }`}>
          {currentPlayer.symbol} - You
        </div>
      </div>
    );
  }
  
  return (
    <div className="turn-indicator">
      <div className={`player-badge player-x ${xIsNext ? 'active' : ''}`}>
        X {gameMode === 'easy' || gameMode === 'hard' ? '(You)' : ''}
      </div>
      <div className={`player-badge player-o ${!xIsNext ? 'active' : ''}`}>
        O {gameMode === 'easy' || gameMode === 'hard' ? '(AI)' : ''}
      </div>
    </div>
  );
};

// Game Mode Selector component
const GameModeSelector = ({ gameMode, onModeChange }) => {
  return (
    <div className="game-mode-selector">
      <h3>Game Mode</h3>
      <div className="mode-options">
        <label className="mode-option">
          <input
            type="radio"
            value="human"
            checked={gameMode === 'human'}
            onChange={(e) => onModeChange(e.target.value)}
          />
          Human vs Human
        </label>
        <label className="mode-option">
          <input
            type="radio"
            value="easy"
            checked={gameMode === 'easy'}
            onChange={(e) => onModeChange(e.target.value)}
          />
          Easy AI
        </label>
        <label className="mode-option">
          <input
            type="radio"
            value="hard"
            checked={gameMode === 'hard'}
            onChange={(e) => onModeChange(e.target.value)}
          />
          Hard AI
        </label>
        <label className="mode-option">
          <input
            type="radio"
            value="online"
            checked={gameMode === 'online'}
            onChange={(e) => onModeChange(e.target.value)}
          />
          Online Multiplayer
        </label>
      </div>
    </div>
  );
};

// Main App component
const App = () => {
  // Initialize state for the board (9 squares)
  const [squares, setSquares] = useState(Array(9).fill(null));
  // Track whose turn it is (X starts)
  const [xIsNext, setXIsNext] = useState(true);
  // Track game mode
  const [gameMode, setGameMode] = useState('human');
  // Track if AI is thinking
  const [aiThinking, setAiThinking] = useState(false);
  // Track API errors
  const [error, setError] = useState(null);
  // Track loading state
  const [isLoading, setIsLoading] = useState(false);
  // Track scores
  const [scores, setScores] = useState({ X: 0, O: 0, draws: 0 });
  // Track move count for the current game
  const [moveCount, setMoveCount] = useState(0);
  // Track current game ID if saved
  const [currentGameId, setCurrentGameId] = useState(null);
  
  // Online multiplayer state
  const [socket, setSocket] = useState(null);
  const [roomCode, setRoomCode] = useState(null);
  const [roomName, setRoomName] = useState(null);
  const [players, setPlayers] = useState([]);
  const [currentPlayer, setCurrentPlayer] = useState(null);
  const [isInRoom, setIsInRoom] = useState(false);
  const socketRef = useRef(null);

  // Handle click on a square
  const handleClick = async (i) => {
    // Check if there's already a winner
    const currentWinner = calculateWinner(squares);
    
    // Don't allow clicks if game is over, AI is thinking or loading
    if (currentWinner || squares.every(square => square !== null) || aiThinking || isLoading) {
      return;
    }
    
    // Handle online multiplayer moves
    if (gameMode === 'online') {
      if (!socketRef.current || !roomCode) {
        setError('Not connected to room');
        return;
      }
      
      // Check if it's the player's turn
      const expectedSymbol = xIsNext ? 'X' : 'O';
      if (!currentPlayer || currentPlayer.symbol !== expectedSymbol) {
        return; // Not your turn
      }
      
      // Check if square is already filled
      if (squares[i]) {
        return;
      }
      
      // Send move to server via socket
      socketRef.current.emit('make-move', {
        roomCode,
        index: i
      });
      return;
    }
    
    // Create a copy of the squares array
    const newSquares = [...squares];
    
    // Return early if there's a winner or the square is already filled
    if (newSquares[i]) {
      return;
    }
    
    // In AI mode, prevent human from playing as O
    if ((gameMode === 'easy' || gameMode === 'hard') && !xIsNext) {
      return;
    }
    
    // Handle local human vs human mode without server calls
    if (gameMode === 'human') {
      // Make the move locally
      newSquares[i] = xIsNext ? 'X' : 'O';
      setSquares(newSquares);
      setXIsNext(!xIsNext);
      setMoveCount(moveCount + 1);
      
      // Check if game is complete
      const winner = calculateWinner(newSquares);
      const isDraw = !winner && newSquares.every(square => square !== null);
      
      if (winner || isDraw) {
        // Game is complete - optionally save to server for history
        // For now, we'll keep it purely local
      }
      
      return;
    }
    
    // Handle AI modes with server calls
    try {
      setIsLoading(true);
      setError(null);
      
      // Increment move count
      const nextMoveCount = moveCount + 1;
      setMoveCount(nextMoveCount);
      
      // Make API call to validate and make the move
      const response = await fetch(`${API_URL}/make-move`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          squares: newSquares,
          index: i,
          player: xIsNext ? 'X' : 'O',
          gameMode: gameMode,
          moveNumber: nextMoveCount
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to make move');
      }
      
      const data = await response.json();
      
      // Update state with validated move
      setSquares(data.squares);
      setXIsNext(!xIsNext);
      
      // If game is complete and saved, store the game ID
      if (data.gameId) {
        setCurrentGameId(data.gameId);
      }
    } catch (err) {
      setError(err.message);
      console.error('Error making move:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Make AI move
  const makeAiMove = async () => {
    if (aiThinking || isLoading) {
      return;
    }
    
    try {
      setAiThinking(true);
      setIsLoading(true);
      setError(null);
      
      // Random delay between 300-1000ms to simulate "thinking"
      const delay = Math.random() * 700 + 300;
      await new Promise(resolve => setTimeout(resolve, delay));
      
      // Make API call to get AI move
      const response = await fetch(`${API_URL}/ai-move`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          squares,
          difficulty: gameMode
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to get AI move');
      }
      
      const data = await response.json();
      
      // Make the AI move
      const aiMoveResponse = await fetch(`${API_URL}/make-move`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          squares,
          index: data.move,
          player: 'O'
        }),
      });
      
      if (!aiMoveResponse.ok) {
        const errorData = await aiMoveResponse.json();
        throw new Error(errorData.error || 'Failed to make AI move');
      }
      
      const moveData = await aiMoveResponse.json();
      
      // Update state with AI move
      setSquares(moveData.squares);
      setXIsNext(true);
    } catch (err) {
      setError(err.message);
      console.error('Error making AI move:', err);
    } finally {
      setAiThinking(false);
      setIsLoading(false);
    }
  };

  // Socket.IO connection management
  const connectSocket = () => {
    if (socketRef.current) {
      socketRef.current.disconnect();
    }
    
    const newSocket = io(SOCKET_URL);
    socketRef.current = newSocket;
    setSocket(newSocket);
    
    // Socket event handlers
    newSocket.on('room-created', (data) => {
      setRoomCode(data.roomCode);
      setRoomName(data.roomName);
      setCurrentPlayer(data.player);
      setPlayers(data.players || [data.player]);
      setSquares(data.gameState.squares);
      setXIsNext(data.gameState.xIsNext);
      setIsInRoom(true);
      setIsLoading(false);
      setError(null);
    });
    
    newSocket.on('room-joined', (data) => {
      setRoomCode(data.roomCode);
      setRoomName(data.roomName);
      setCurrentPlayer(data.player);
      setPlayers(data.players || [data.player]);
      setSquares(data.gameState.squares);
      setXIsNext(data.gameState.xIsNext);
      setIsInRoom(true);
      setIsLoading(false);
      setError(null);
    });
    
    newSocket.on('player-joined', (data) => {
      setPlayers(data.players || []);
      setSquares(data.gameState.squares);
      setXIsNext(data.gameState.xIsNext);
    });
    
    newSocket.on('game-updated', (data) => {
      setSquares(data.gameState.squares);
      setXIsNext(data.gameState.xIsNext);
      setError(null);
      
      // Update move count if provided
      if (data.lastMove && data.lastMove.moveNumber) {
        setMoveCount(data.lastMove.moveNumber);
      }
      
      // If game is complete and saved, store the game ID
      if (data.gameId) {
        setCurrentGameId(data.gameId);
      }
    });
    
    newSocket.on('game-reset', (data) => {
      setSquares(data.gameState.squares);
      setXIsNext(data.gameState.xIsNext);
      setError(null);
      setMoveCount(0);
      setCurrentGameId(null);
    });
    
    newSocket.on('player-left', (data) => {
      setPlayers(prev => prev.filter(p => p.id !== data.player.id));
      setError(`${data.player.name} left the room`);
    });
    
    newSocket.on('error', (data) => {
      setError(data.message);
      setIsLoading(false);
    });
    
    return newSocket;
  };
  
  // Online multiplayer functions
  const handleCreateRoom = (data) => {
    setIsLoading(true);
    setError(null);
    const socket = connectSocket();
    socket.emit('create-room', data);
  };
  
  const handleJoinRoom = (data) => {
    setIsLoading(true);
    setError(null);
    const socket = connectSocket();
    socket.emit('join-room', data);
  };
  
  const handleLeaveRoom = () => {
    if (socketRef.current) {
      socketRef.current.disconnect();
    }
    setSocket(null);
    setRoomCode(null);
    setRoomName(null);
    setPlayers([]);
    setCurrentPlayer(null);
    setIsInRoom(false);
    resetGame();
  };
  
  const handleCopyRoomCode = () => {
    if (roomCode) {
      navigator.clipboard.writeText(roomCode).then(() => {
        // Could add a toast notification here
        alert('Room code copied to clipboard!');
      }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = roomCode;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        alert('Room code copied to clipboard!');
      });
    }
  };

  // Effect to trigger AI moves
  useEffect(() => {
    if ((gameMode === 'easy' || gameMode === 'hard') && !xIsNext && !aiThinking && !isLoading) {
      // Check if there are empty squares and no winner
      const winner = calculateWinner(squares);
      if (!winner && squares.includes(null)) {
        makeAiMove();
      }
    }
  }, [gameMode, xIsNext, squares, aiThinking, isLoading]);
  
  // Cleanup socket on unmount
  useEffect(() => {
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  // Reset the game
  const resetGame = () => {
    if (gameMode === 'online' && socketRef.current && roomCode) {
      socketRef.current.emit('reset-game', { roomCode });
    } else {
      setSquares(Array(9).fill(null));
      setXIsNext(true);
      setAiThinking(false);
      setError(null);
      setIsLoading(false);
      setScoreUpdated(false);
      setMoveCount(0);
      setCurrentGameId(null);
    }
  };

  // Handle game mode change
  const handleModeChange = (mode) => {
    // If leaving online mode, disconnect from room
    if (gameMode === 'online' && mode !== 'online') {
      handleLeaveRoom();
    }
    setGameMode(mode);
    if (mode !== 'online') {
      resetGame();
    }
  };

  // Calculate the winner (client-side for UI purposes)
  const calculateWinner = (squares) => {
    // All possible winning combinations
    const lines = [
      [0, 1, 2], // top row
      [3, 4, 5], // middle row
      [6, 7, 8], // bottom row
      [0, 3, 6], // left column
      [1, 4, 7], // middle column
      [2, 5, 8], // right column
      [0, 4, 8], // diagonal top-left to bottom-right
      [2, 4, 6]  // diagonal top-right to bottom-left
    ];
    
    // Check each winning combination
    for (let i = 0; i < lines.length; i++) {
      const [a, b, c] = lines[i];
      // If all three squares in a line have the same value (and not null)
      if (squares[a] && squares[a] === squares[b] && squares[a] === squares[c]) {
        return {
          winner: squares[a], // Return the winner (X or O)
          line: [a, b, c],
          lineIndex: i
        };
      }
    }
    
    return null; // No winner
  };

  // Calculate the winner
  const winnerInfo = calculateWinner(squares);
  const winner = winnerInfo ? winnerInfo.winner : null;
  
  // Track if score has been updated for current game
  const [scoreUpdated, setScoreUpdated] = useState(false);
  
  // Update scores when game ends
  useEffect(() => {
    if (!scoreUpdated) {
      if (winner) {
        setScores(prev => ({ ...prev, [winner]: prev[winner] + 1 }));
        setScoreUpdated(true);
      } else if (squares.every(square => square !== null) && !winner) {
        setScores(prev => ({ ...prev, draws: prev.draws + 1 }));
        setScoreUpdated(true);
      }
    }
  }, [winner, squares, scoreUpdated]);
  
  // Determine status message
  let status;
  if (error) {
    status = `Error: ${error}`;
  } else if (winner) {
    if (gameMode === 'easy' || gameMode === 'hard') {
      status = winner === 'X' ? 'You Win!' : 'AI Wins!';
    } else if (gameMode === 'online' && currentPlayer) {
      status = winner === currentPlayer.symbol ? 'You Win!' : 'You Lose!';
    } else {
      status = `Winner: ${winner}`;
    }
  } else if (squares.every(square => square !== null)) {
    status = 'Draw!';
  } else if (aiThinking || isLoading) {
    if (gameMode === 'online') {
      status = 'Connecting...';
    } else {
      status = 'AI Thinking...';
    }
  } else {
    if (gameMode === 'easy' || gameMode === 'hard') {
      status = xIsNext ? 'Your Turn (X)' : 'AI Turn (O)';
    } else if (gameMode === 'online') {
      if (!isInRoom) {
        status = 'Select Create Room or Join Room';
      } else if (players.length < 2) {
        status = 'Waiting for another player...';
      } else if (currentPlayer) {
        const isMyTurn = (xIsNext && currentPlayer.symbol === 'X') || (!xIsNext && currentPlayer.symbol === 'O');
        status = isMyTurn ? `Your Turn (${currentPlayer.symbol})` : `Opponent's Turn`;
      } else {
        status = 'Connecting...';
      }
    } else {
      status = `Next player: ${xIsNext ? 'X' : 'O'}`;
    }
  }

  // State to toggle game history view
  const [showHistory, setShowHistory] = useState(false);

  return (
    <div className="game">
      <h1>Tic Tac Toe</h1>
      
      <div className="left-panel">
        <GameModeSelector gameMode={gameMode} onModeChange={handleModeChange} />
        {(gameMode !== 'online' || (gameMode === 'online' && isInRoom)) && (
          <ScoreTracker scores={scores} />
        )}
        <button 
          className="primary-button" 
          style={{ marginTop: '1rem' }}
          onClick={() => setShowHistory(!showHistory)}
        >
          {showHistory ? 'Hide History' : 'Show History'}
        </button>
      </div>
      
      <div className="game-content">
        {gameMode === 'online' && !isInRoom && (
          <RoomSetup 
            onCreateRoom={handleCreateRoom}
            onJoinRoom={handleJoinRoom}
            isLoading={isLoading}
          />
        )}
        
        {(gameMode !== 'online' || (gameMode === 'online' && isInRoom)) && (
          <>
            <div className="game-status-bar">
              <TurnIndicator xIsNext={xIsNext} gameMode={gameMode} currentPlayer={currentPlayer} />
              <div className={`status ${error ? 'error' : ''} ${winner ? 'winner' : ''}`}>{status}</div>
            </div>
            <Board 
              squares={squares} 
              onClick={handleClick} 
              disabled={
                winner !== null ||
                squares.every(square => square !== null) ||
                aiThinking || 
                isLoading || 
                ((gameMode === 'easy' || gameMode === 'hard') && !xIsNext) ||
                (gameMode === 'online' && (!currentPlayer || players.length < 2 || 
                  (xIsNext && currentPlayer.symbol !== 'X') || 
                  (!xIsNext && currentPlayer.symbol !== 'O')))
              }
            />
            <button className="reset-button" onClick={resetGame}>
              Reset Game
            </button>
          </>
        )}
      </div>
      
      <div className="right-panel">
        {gameMode === 'online' && isInRoom && (
          <RoomInfo 
            roomCode={roomCode}
            roomName={roomName}
            players={players}
            currentPlayer={currentPlayer}
            onLeaveRoom={handleLeaveRoom}
            onCopyRoomCode={handleCopyRoomCode}
          />
        )}
      </div>
      
      {showHistory && (
        <GameHistory />
      )}
    </div>
  );
};

export default App;