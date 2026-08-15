const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  
  // Correction workflow
  corrections: {
    listPending: () => ipcRenderer.invoke('corrections:list-pending'),
    promoteToConfirmed: (id_ppss) => ipcRenderer.invoke('corrections:promote-to-confirmed', id_ppss),
    applyConfirmed: () => ipcRenderer.invoke('corrections:apply-confirmed'),
    checkUpdates: () => ipcRenderer.invoke('corrections:check-updates'),
    triggerLoadData: () => ipcRenderer.invoke('corrections:trigger-load-data'),
  }
});