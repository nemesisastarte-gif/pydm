// PyDM Bridge - Popup Script
const WS_URL = "ws://127.0.0.1:9090";

const statusEl = document.getElementById("status");
const lastDlEl = document.getElementById("last-dl");
const btnReconnect = document.getElementById("btn-reconnect");
const btnTest = document.getElementById("btn-test");

let ws = null;

function updateStatus(connected) {
  if (connected) {
    statusEl.textContent = "Connecté à PyDM";
    statusEl.className = "status connected";
  } else {
    statusEl.textContent = "Déconnecté";
    statusEl.className = "status disconnected";
  }
}

function connect() {
  if (ws) {
    try { ws.close(); } catch(e) {}
  }
  
  try {
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
      updateStatus(true);
      console.log("[Popup] Connecté");
    };
    
    ws.onclose = () => {
      updateStatus(false);
      console.log("[Popup] Déconnecté");
    };
    
    ws.onerror = () => {
      updateStatus(false);
    };
    
    ws.onmessage = (event) => {
      console.log("[Popup] Message:", event.data);
    };
    
  } catch(e) {
    updateStatus(false);
  }
}

btnReconnect.addEventListener("click", connect);

btnTest.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      action: "ping",
      timestamp: Date.now()
    }));
    lastDlEl.textContent = "Test envoyé !";
  } else {
    lastDlEl.textContent = "Non connecté. Lancez 'pydm ws-server'";
    updateStatus(false);
  }
});

// Vérifier périodiquement la connexion
setInterval(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    updateStatus(false);
  }
}, 5000);

// Connexion initiale
connect();
