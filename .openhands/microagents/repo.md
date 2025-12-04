# Repository Description: oh-tic-tac-toe

## Overview
This repository contains a full-stack Tic Tac Toe game with an Express.js server backend and a React frontend. The game supports both multiplayer mode via Socket.IO and single-player mode against an AI with different difficulty levels.

## Repository Structure
- `/client`: React frontend application
  - `/src`: Source code for the React application
    - `App.js`: Main React component with game logic
    - `index.js`: Entry point for the React application
    - `styles.css`: Styling for the application
  - `/public`: Static files including index.html
  - `webpack.config.js`: Webpack configuration for building the client
  - `package.json`: Dependencies and scripts for the client

- `/server`: Express.js backend
  - `index.js`: Server code with game logic, API endpoints, and Socket.IO implementation
  - `package.json`: Dependencies and scripts for the server

- Root files:
  - `package.json`: Root package with scripts to install dependencies and run the application
  - `Procfile`: Configuration for deployment platforms like Heroku
  - `README.md`: Project documentation

## Technologies Used
- **Frontend**:
  - React 19.1.0
  - Socket.IO Client 4.8.1
  - Webpack 5.100.2 for bundling
  - Babel for JavaScript transpilation

- **Backend**:
  - Express 4.18.2
  - Socket.IO 4.8.1 for real-time communication
  - Node.js (requires v18.0.0 or higher)

## Features
1. **Multiplayer Mode**: Play against another player in real-time using Socket.IO
2. **Single-player Mode**: Play against an AI with two difficulty levels (easy and hard)
3. **Room System**: Create and join game rooms with unique codes
4. **Game Logic**: Complete implementation of Tic Tac Toe rules with win detection
5. **Responsive Design**: Works on various screen sizes

## Game Logic
- The game uses a 3x3 grid represented as an array of 9 elements
- Players take turns placing X or O on the board
- The game checks for winning combinations after each move
- The AI uses different strategies based on difficulty level:
  - Easy: Makes random valid moves
  - Hard: Uses strategic logic to play optimally

## How to Run the Application

### Prerequisites
- Node.js v18.0.0 or higher
- npm (comes with Node.js)

### Installation
1. Clone the repository
2. Install all dependencies:
   ```
   npm run install-all
   ```
   This will install dependencies for the root project, client, and server.

### Running in Development Mode
1. Build the client and start the server:
   ```
   npm start
   ```
   This will:
   - Build the React client using Webpack
   - Start the Express server on port 12000 (or the port specified in the PORT environment variable)

2. Access the application at http://localhost:12000

### Running on OpenHands
When running on OpenHands, use port 12000:
```
npm start
```
The application will be accessible at the provided host URL.

## API Endpoints
- `GET /api/health`: Health check endpoint
- `POST /api/ai-move`: Get an AI move based on the current board state and difficulty
- `POST /api/make-move`: Make a move and get the updated board state

## Socket.IO Events
- `create-room`: Create a new game room
- `join-room`: Join an existing game room
- `make-move`: Make a move in a multiplayer game
- `reset-game`: Reset the game board
- `disconnect`: Handle player disconnection

## Deployment
The application is configured for deployment to platforms like Render with minimal setup:
- Build Command: `npm run install-all && npm run build`
- Start Command: `npm run start-server`