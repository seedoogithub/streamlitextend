import * as msgpack from '@msgpack/msgpack';

class WebSocketWrapper {
  static instances = {};
  listeners = [];

  constructor(port, comopnent_id, spinner = false) {
    this.ip = window.location.hostname;
    this.port = port;
    this.comopnent_id = comopnent_id;
    this.spinner = spinner;
    this.connect();
  }

  static getInstance(port, comopnent_id, spinner = false) {
    const key = `${port}:${comopnent_id}`;
    console.log('Getting key: ', key);
    if (!WebSocketWrapper.instances[key]) {
      WebSocketWrapper.instances[key] = new WebSocketWrapper(port, comopnent_id, spinner);
    } else {
      WebSocketWrapper.instances[key].cleanup();
      WebSocketWrapper.instances[key].connect();
    }

    return WebSocketWrapper.instances[key];
  }

  hideSpinner() {
    if (this.spinner) {
      const spinner = document.querySelector('.spinner_custom');
      if (spinner) {
        document.body.removeChild(spinner);
      }
    }
  }

  showSpinner() {
    const spinner = document.createElement('div');
    spinner.className = 'spinner_custom';
    document.body.appendChild(spinner);
  }

  connect() {
    let wsType = 'wss';
    if (window.location.protocol !== "https:") {
      wsType = 'ws';
    }
    this.ws = new WebSocket(`${wsType}://${this.ip}:${this.port}/ws/${this.comopnent_id}`);
    this.ws.binaryType = 'arraybuffer';

    // Setting up a timeout for the initial connection
    const connectionTimeout = setTimeout(() => {
      if (this.ws.readyState !== WebSocket.OPEN) {
        console.error("Connection timed out after 15 seconds.");
        console.log("Connection timed out after 15 seconds.");
        this.ws.close();
      }
    }, 15000);  // Reduced timeout to 15 seconds

    this.ws.onopen = (event) => {
      clearTimeout(connectionTimeout); // Clearing the timeout once connected
      console.log("Connection opened:", event);
    };

    this.ws.onerror = (error) => {
      clearTimeout(connectionTimeout); // Clearing the timeout on error
      console.log("WebSocket Error:", error);
      this.cleanup();  // Custom method to clean up state
      setTimeout(() => {
        this.connect();
      }, 1000);  // Attempt to reconnect after a short delay
    };

    this.ws.onclose = (event) => {
      console.log("Connection closed:", event);
      this.cleanup();  // Custom method to clean up state
      setTimeout(() => {
        this.connect();
      }, 1000);  // Attempt to reconnect after a short delay
    };

    this.ws.onmessage = (event) => {
      console.log('Got message');
      this.hideSpinner();
      console.log(event);

      if (typeof event.data === 'string') {
        const message = JSON.parse(event.data);
        this.listeners.forEach(listener => listener(message));
      } else {
        const data = msgpack.decode(new Uint8Array(event.data));
        this.listeners.forEach(listener => listener(data));
      }
    };
  }

  cleanup() {
    if (this.ws) {
      this.ws.onopen = this.ws.onclose = this.ws.onerror = this.ws.onmessage = null;
      this.ws = null;
    }
  }

  sendData(data) {
    if (this.spinner) {
      this.showSpinner();
    }

    const sendWhenReady = () => {
      if (this.ws.readyState === WebSocket.OPEN) {
        const jsonString = JSON.stringify(data);
        this.ws.send(jsonString);
        console.log("Data sent to server:", jsonString);
      } else if (this.ws.readyState === WebSocket.CONNECTING) {
        console.warn("WebSocket connection is opening", this.comopnent_id);
        setTimeout(sendWhenReady, 1000);  // Reduced timeout to 1 second
      } else {
        console.error("WebSocket connection is closed, reconnecting");
        this.connect();
        setTimeout(sendWhenReady, 1000);  // Wait a bit before retrying to ensure connection
      }
    };

    sendWhenReady();
  }

  addListener(listener) {
    this.sendData({'id': this.comopnent_id});
    this.listeners.push(listener);
  }

  removeListener(listener) {
    const index = this.listeners.indexOf(listener);
    if (index > -1) {
      this.listeners.splice(index, 1);
    }
  }
}

export default WebSocketWrapper;
