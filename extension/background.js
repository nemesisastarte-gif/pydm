// PyDM Bridge - Background Script (Manifest V2)
// Intercepte les téléchargements du navigateur et les transfère à PyDM

const WS_URL = "ws://127.0.0.1:9090";
let ws = null;
let reconnectTimer = null;
let pendingDownloads = [];

// ============================================================
// CONNEXION WEBSOCKET AU SERVEUR PYDM LOCAL
// ============================================================

function connectToPyDM() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  if (ws && ws.readyState === WebSocket.CONNECTING) return;
  
  try {
    ws = new WebSocket(WS_URL);
    
    ws.onopen = function() {
      console.log("[PyDM Bridge] Connecte au serveur PyDM");
      while (pendingDownloads.length > 0) {
        var dl = pendingDownloads.shift();
        sendToPyDM(dl);
      }
    };
    
    ws.onclose = function() {
      console.log("[PyDM Bridge] Deconnecte, reconnexion dans 5s...");
      scheduleReconnect();
    };
    
    ws.onerror = function(err) {
      console.log("[PyDM Bridge] Erreur WebSocket:", err);
    };
    
    ws.onmessage = function(event) {
      console.log("[PyDM Bridge] Message recu:", event.data);
    };
    
  } catch (e) {
    console.log("[PyDM Bridge] Impossible de se connecter:", e);
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connectToPyDM, 5000);
}

function sendToPyDM(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
    console.log("[PyDM Bridge] Envoye a PyDM:", data.filename);
    return true;
  } else {
    pendingDownloads.push(data);
    connectToPyDM();
    return false;
  }
}

// ============================================================
// INTERCEPTION DES TELECHARGEMENTS DU NAVIGATEUR
// ============================================================

chrome.downloads.onCreated.addListener(function(downloadItem) {
  console.log("[PyDM Bridge] Telechargement detecte:", downloadItem.url);
  
  var url = downloadItem.url;
  var filename = downloadItem.filename || extractFilename(url);
  
  // Ignorer les URLs non HTTP
  if (url.indexOf("http") !== 0) return;
  
  // Annuler le telechargement du navigateur
  chrome.downloads.cancel(downloadItem.id, function() {
    if (chrome.runtime.lastError) {
      console.log("[PyDM Bridge] Annulation echouee:", chrome.runtime.lastError.message);
      return;
    }
    
    getCookiesForUrl(url, function(cookies) {
      var payload = {
        action: "download",
        url: url,
        filename: filename,
        cookies: cookies,
        referer: downloadItem.referrer || "",
        mime: downloadItem.mime || "",
        timestamp: Date.now()
      };
      sendToPyDM(payload);
    });
  });
});

// ============================================================
// INTERCEPTION DES REQUETES RESEAU
// ============================================================

chrome.webRequest.onHeadersReceived.addListener(
  function(details) {
    var headers = details.responseHeaders || [];
    var contentType = getHeader(headers, "content-type") || "";
    var contentDisposition = getHeader(headers, "content-disposition") || "";
    var contentLength = parseInt(getHeader(headers, "content-length") || "0");
    
    var downloadableTypes = [
      "video/", "audio/", "application/zip", "application/x-rar",
      "application/x-7z", "application/pdf", "application/octet-stream",
      "application/x-iso9660", "application/x-debian-package"
    ];
    
    var isDownloadable = false;
    for (var i = 0; i < downloadableTypes.length; i++) {
      if (contentType.indexOf(downloadableTypes[i]) === 0) {
        isDownloadable = true;
        break;
      }
    }
    
    var hasAttachment = contentDisposition.indexOf("attachment") !== -1;
    var isLargeEnough = contentLength > 1024 * 1024 * 1;
    
    if ((isDownloadable || hasAttachment) && isLargeEnough) {
      var filename = extractFilenameFromDisposition(contentDisposition) || extractFilename(details.url);
      
      console.log("[PyDM Bridge] Fichier detecte via webRequest:", filename, contentType);
      
      var payload = {
        action: "download",
        url: details.url,
        filename: filename,
        fileSize: contentLength,
        cookies: {},
        referer: details.initiator || "",
        mime: contentType,
        timestamp: Date.now()
      };
      
      sendToPyDM(payload);
    }
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

// ============================================================
// MENU CONTEXTUEL (clic droit sur un lien)
// ============================================================

chrome.runtime.onInstalled.addListener(function() {
  chrome.contextMenus.create({
    id: "pydm-download",
    title: "Telecharger avec PyDM",
    contexts: ["link", "video", "audio"]
  });
});

chrome.contextMenus.onClicked.addListener(function(info, tab) {
  if (info.menuItemId === "pydm-download") {
    var url = info.linkUrl || info.srcUrl;
    if (url) {
      getCookiesForUrl(url, function(cookies) {
        sendToPyDM({
          action: "download",
          url: url,
          filename: extractFilename(url),
          cookies: cookies,
          referer: tab ? tab.url : "",
          timestamp: Date.now()
        });
      });
    }
  }
});

// ============================================================
// FONCTIONS UTILITAIRES
// ============================================================

function getCookiesForUrl(url, callback) {
  try {
    chrome.cookies.getAll({ url: url }, function(cookies) {
      var cookieObj = {};
      cookies.forEach(function(c) {
        cookieObj[c.name] = c.value;
      });
      callback(cookieObj);
    });
  } catch (e) {
    callback({});
  }
}

function extractFilename(url) {
  try {
    var parser = document.createElement('a');
    parser.href = url;
    var pathname = parser.pathname;
    var filename = pathname.split("/").pop();
    if (filename && filename.indexOf(".") !== -1) {
      return decodeURIComponent(filename.split("?")[0]);
    }
    return "download_" + parser.hostname + "_" + Date.now() + ".bin";
  } catch (e) {
    return "download_" + Date.now() + ".bin";
  }
}

function extractFilenameFromDisposition(disposition) {
  var match = disposition.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i);
  if (match) return decodeURIComponent(match[1]);
  var match2 = disposition.match(/filename=["']?([^"';]+)["']?/i);
  if (match2) return match2[1];
  return null;
}

function getHeader(headers, name) {
  for (var i = 0; i < headers.length; i++) {
    if (headers[i].name.toLowerCase() === name.toLowerCase()) {
      return headers[i].value;
    }
  }
  return null;
}

// ============================================================
// DEMARRAGE
// ============================================================

connectToPyDM();
console.log("[PyDM Bridge] Extension demarree");
