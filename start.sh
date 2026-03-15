#!/bin/bash

echo "=============================================="
echo "       Starting Ledger AI Services..."
echo "=============================================="

# Function to handle cleanup on exit
cleanup() {
    echo "Stopping all services..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM to run the cleanup function
trap cleanup SIGINT SIGTERM

echo "1. Starting Python Backend API..."
cd backend || exit
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
uvicorn backend:app --reload &
BACKEND_PID=$!
cd ..

echo "2. Starting React Frontend..."
cd frontend || exit
npm run dev &
FRONTEND_PID=$!
cd ..

echo "=============================================="
echo "   All services are running in the background!"
echo "   * Backend is running on Port 8000"
echo "   * Frontend is running on Port 5173"
echo "   Press Ctrl+C to stop all services."
echo "=============================================="

# Wait for background processes to keep the script running
wait $BACKEND_PID $FRONTEND_PID
