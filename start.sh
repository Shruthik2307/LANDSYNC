#!/bin/bash
# Start both backend and frontend concurrently

echo "Starting LANDSYNC Backend..."
cd backend && python main.py &
BACKEND_PID=$!

echo "Starting LANDSYNC Frontend..."
cd .. && npm run dev &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both services"

# Trap Ctrl+C and kill both processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT

# Wait for both processes
wait
