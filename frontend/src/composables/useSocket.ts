import { io, Socket } from "socket.io-client";

// Single shared socket instance across all components
let socket: Socket | null = null;

const BACKEND_URL = "http://localhost:8000";

export function getSocket(): Socket {
  if (!socket) {
    socket = io(BACKEND_URL, {
      transports: ["websocket"],
      autoConnect: false,
    });
  }
  return socket;
}
