# AI Scarecrow

![Scarecrow Preview](https://github.com/TCrawley11/hack_canada_2026/blob/main/frontend/public/scarecrow%20preview.gif?raw=true)

**An adaptive AI scarecrow that detects predators and intruders and dynamically scares them away to protect livestock.**

## Why This Matters

This project was built for **Hack Canada 2026** under the theme **“Solving Problems Canadians Face.”**

Canada has vast rural farmland that sits alongside dense wildlife populations. Farmers regularly lose livestock and crops to predators and pests, and traditional scarecrows quickly become ineffective as animals learn to ignore them.

Our scarecrow explores a **low-cost, AI-powered deterrent system** that adapts to different threats in real time while remaining humane to wildlife.

Instead of static scare tactics, our scarecrow detects what is approaching and deploys the **most effective deterrent for that specific animal or intruder**.

## What It Does

Our scarecrow is a smart farm sentinel that:

- Detects animals and humans using a webcam and ML detection
- Identifies species (e.g. raccoon, coyote, birds, humans)
- Deploys **adaptive deterrents** such as predator sounds or voice warnings for human intruders
- Logs detections and responses in a **live monitoring dashboard**
- Uses **AI voice generation** for human intruder warnings

## Example Deterrents

- Crow → Hawk screech  
- Raccoon → Dog bark  
- Deer → Human voice warning  
- Human intruder → Custom human voice warning

## Dashboard Features

- Live webcam feed  
- Detection log with timestamps and deterrent action
- Manual scare soundboard

## How to Run

### Backend

1. Create a `.env` file in the `backend/` directory with your API keys:
   ```
   GEMINI_API_KEY=key
   ELEVENLABS_API_KEY=key
   ```

2. Navigate to the backend directory and sync dependencies:
   ```bash
   cd backend
   uv sync
   ```

3. Start the FastAPI server:
   ```bash
   fastapi dev
   ```

4. In a new terminal, activate the virtual environment and run the ML detection:
   ```bash
   cd backend/ml
   source venv/bin/activate
   python yolo.py --camera 0  # or --camera 1 depending on your webcam
   ```

### Frontend

1. Navigate to the frontend directory and install dependencies:
   ```bash
   cd frontend
   pnpm install
   ```

2. Start the development server:
   ```bash
   pnpm run dev
   ```

3. Open your browser to the URL shown in the terminal (usually `http://localhost:5173`)

## Why Adaptive Scarecrows?

Traditional scarecrows fail because animals quickly become accustomed to them.

Our scarecrow adapts by:

- Detecting the **specific animal species**
- Selecting the **most effective deterrent**
- Rotating deterrents to prevent habituation
- Logging encounters to understand **farm threat patterns**

## Why This Is Relevant in Canada

- Canada has **massive rural farmland regions**
- Farms are often located near **forests and wildlife habitats**
- Livestock losses from predators are a recurring issue
- Humane wildlife deterrence is preferred over harmful control methods

Common farm predators include:

- Coyotes  
- Foxes  
- Raccoons  
- Birds  
- Deer  

## Tech Stack

Frontend:
- React  
- Vite  
- pnpm  
- WebSockets  

Backend:
- ML object detection  
- Webcam video input  
- Event streaming to frontend  

Integrations:
- Gemini  
- ElevenLabs voice generation  

## Hardware (Hackathon MVP)

- Tripod scarecrow stand  
- Halloween mask  
- Bluetooth speaker  
- Logitech Brio webcam  

## Demo

1. Webcam detects animal or human  
2. ML identifies the species  
3. Our scarecrow selects a deterrent  
4. Sound or voice plays through the scarecrow  
5. Event appears on the dashboard  

## Future Ideas

- Farm-wide threat heatmaps  
- Solar-powered remote units  
- Multiple scarecrow network across fields  
- Mobile alerts for farmers  
- Learning which deterrents work best  

---

Built at **Hack Canada 2026** in Waterloo 🇨🇦
