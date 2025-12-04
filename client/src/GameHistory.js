import React, { useState, useEffect } from 'react';

// API URL - adjust if needed
const API_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:12000/api' 
  : '/api';

const GameHistory = () => {
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedGame, setSelectedGame] = useState(null);
  const [gameDetails, setGameDetails] = useState(null);

  // Fetch game history on component mount
  useEffect(() => {
    fetchGameHistory();
  }, []);

  // Fetch game history from the server
  const fetchGameHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/games`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch game history');
      }
      
      const data = await response.json();
      setGames(data.games || []);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching game history:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch details for a specific game
  const fetchGameDetails = async (gameId) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/games/${gameId}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch game details');
      }
      
      const data = await response.json();
      setGameDetails(data);
      setSelectedGame(gameId);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching game details:', err);
    } finally {
      setLoading(false);
    }
  };

  // Format date for display
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  // Render game result
  const renderGameResult = (game) => {
    if (game.is_draw) {
      return 'Draw';
    }
    if (game.winner) {
      return `${game.winner} Won`;
    }
    return 'Incomplete';
  };

  // Render game mode
  const renderGameMode = (mode) => {
    switch (mode) {
      case 'easy':
        return 'vs Easy AI';
      case 'hard':
        return 'vs Hard AI';
      case 'human':
        return 'Local Multiplayer';
      case 'online':
        return 'Online Multiplayer';
      default:
        return mode;
    }
  };

  // Render a board from moves
  const renderBoard = (moves) => {
    // Create an empty board
    const board = Array(9).fill(null);
    
    // Apply moves in order
    moves.forEach(move => {
      board[move.position] = move.player_symbol;
    });
    
    return (
      <div className="history-board">
        {board.map((value, index) => (
          <div key={index} className="history-square">
            {value}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="game-history">
      <h2>Game History</h2>
      
      {error && <div className="error">{error}</div>}
      
      {loading ? (
        <div className="loading">Loading...</div>
      ) : (
        <div className="history-content">
          {games.length === 0 ? (
            <div className="no-games">No games played yet</div>
          ) : (
            <div className="history-container">
              <div className="games-list">
                <h3>Recent Games</h3>
                <ul>
                  {games.map(game => (
                    <li 
                      key={game.id} 
                      className={selectedGame === game.id ? 'selected' : ''}
                      onClick={() => fetchGameDetails(game.id)}
                    >
                      <div className="game-item">
                        <div className="game-mode">{renderGameMode(game.game_mode)}</div>
                        <div className="game-result">{renderGameResult(game)}</div>
                        <div className="game-date">{formatDate(game.completed_at)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
              
              {gameDetails && (
                <div className="game-details">
                  <h3>Game Details</h3>
                  <div className="detail-item">
                    <span className="label">Mode:</span>
                    <span className="value">{renderGameMode(gameDetails.game.game_mode)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Player X:</span>
                    <span className="value">{gameDetails.game.player_x}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Player O:</span>
                    <span className="value">{gameDetails.game.player_o}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Result:</span>
                    <span className="value">{renderGameResult(gameDetails.game)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Date:</span>
                    <span className="value">{formatDate(gameDetails.game.completed_at)}</span>
                  </div>
                  
                  <h4>Final Board</h4>
                  {gameDetails.moves && gameDetails.moves.length > 0 ? (
                    renderBoard(gameDetails.moves)
                  ) : (
                    <div className="no-moves">No moves recorded</div>
                  )}
                  
                  <h4>Moves</h4>
                  {gameDetails.moves && gameDetails.moves.length > 0 ? (
                    <ul className="moves-list">
                      {gameDetails.moves.map(move => (
                        <li key={move.id}>
                          {move.move_number}. {move.player_symbol} placed at position {move.position}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="no-moves">No moves recorded</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      <button onClick={fetchGameHistory} className="refresh-button">
        Refresh
      </button>
    </div>
  );
};

export default GameHistory;