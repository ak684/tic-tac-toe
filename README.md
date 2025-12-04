# Tic Tac Toe Game

A simple full-stack tic-tac-toe game with Express server and React frontend.

> **Note**: This repository is configured for automatic deployment to Render from the main branch. For Docker deployment support, check out the `support-docker` branch.


## Technical Assessment Reflections

**Instructions for running the app**
See below :D

**A brief description of your approach**
I knew I wanted to be able to hand over a public link to my work so my approach was to use typescript, react, express and render since I have familiarity with working quickly with those tools. From there my though process was to work incrementally with the most important goal being to get something simple and full stack working and deployable ASAP. Once I had something deployable, I continued from there trying to add more fun features and explore persistance and even some initial docker deployment support. So far the app has, 'easy AI' 'hard AI' and online multiplayer rooms supported by Socket IO, and game history supported by sqllite persistance which I think are cool features.

**What AI tools you used and how**
I used Openhands CLI and Openhands Cloud ui. My goal there was to dogfood as much as possible so I can come into a review interview with what I hope are genuine and valuable thoughts and feedback not only on my approach but also the product and any bugs I may run into or delightful moments.

**Anything that didn’t go as planned or you'd improve with more time**
If I had more time I'd add fun features like user auth, Elo scores, and other things like that. Also I realized with 1/3 time left I could run multiple OH workstreams in parallel, so I'd try to do that even more in the future if I had more time (although there's definitely some mental management to be had with 'live' kicking off code workstreams under pressure to be productive but also attempt to minimize merge conflicts)

**Development Video**
https://www.loom.com/share/c6dcb5f5a86e43389bd010c34e159fac?sid=bf188116-c252-4d4d-aed4-4deba7d7b7c8

**Live App on Render**
https://oh-tic-tac-toe.onrender.com/

## Local Development

1. Clone the repository
2. Install dependencies:
   ```
   npm run install-all
   ```
3. Build and start the server:
   ```
   npm start
   ```
4. Access the game at http://localhost:12000 (or the port specified in your environment)

## Deployment to Render

This application is ready to deploy to Render with minimal configuration:

1. Create a new Web Service in Render
2. Connect your GitHub repository
3. Use the following settings:
   - **Build Command**: `npm run install-all && npm run build`
   - **Start Command**: `npm run start-server`
   - **Environment Variables**: None required (Render will set PORT automatically)

Render will automatically detect the Node.js environment and deploy your application.

## Docker Support

For users who prefer Docker deployment, we have a dedicated branch with full Docker support:

```bash
git checkout support-docker
```

The `support-docker` branch includes:
- Optimized multi-stage Dockerfile
- docker-compose.yml for easy local testing
- Complete Docker deployment instructions

This allows you to run the application in a containerized environment with just:
```bash
docker-compose up
```

> **Important**: The main branch is connected to Render for automatic deployment. Docker files are kept in a separate branch to avoid any potential conflicts with the production deployment pipeline.
