const { db } = require('../db');

/**
 * Save a completed game to the database
 * @param {Object} gameData - Game data to save
 * @returns {Number} - ID of the inserted game
 */
function saveGame(gameData) {
  const stmt = db.prepare(`
    INSERT INTO games (game_mode, player_x, player_o, winner, is_draw, completed_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
  `);
  
  const result = stmt.run(
    gameData.gameMode,
    gameData.playerX,
    gameData.playerO,
    gameData.winner,
    gameData.isDraw ? 1 : 0
  );
  
  return result.lastInsertRowid;
}

/**
 * Save a move in a game
 * @param {Object} moveData - Move data to save
 * @returns {Object} - Result of the insert operation
 */
function saveMove(moveData) {
  const stmt = db.prepare(`
    INSERT INTO game_moves (game_id, player_symbol, position, move_number)
    VALUES (?, ?, ?, ?)
  `);
  
  return stmt.run(
    moveData.gameId,
    moveData.playerSymbol,
    moveData.position,
    moveData.moveNumber
  );
}

/**
 * Get game history with optional limit
 * @param {Number} limit - Maximum number of games to return
 * @returns {Array} - Array of game objects
 */
function getGameHistory(limit = 10) {
  return db.prepare(`
    SELECT * FROM games
    ORDER BY completed_at DESC
    LIMIT ?
  `).all(limit);
}

/**
 * Get moves for a specific game
 * @param {Number} gameId - ID of the game
 * @returns {Array} - Array of move objects
 */
function getGameMoves(gameId) {
  return db.prepare(`
    SELECT * FROM game_moves
    WHERE game_id = ?
    ORDER BY move_number
  `).all(gameId);
}

/**
 * Get a specific game by ID
 * @param {Number} gameId - ID of the game
 * @returns {Object} - Game object
 */
function getGameById(gameId) {
  return db.prepare(`
    SELECT * FROM games
    WHERE id = ?
  `).get(gameId);
}

module.exports = {
  saveGame,
  saveMove,
  getGameHistory,
  getGameMoves,
  getGameById
};