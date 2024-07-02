import * as msgpack from '@msgpack/msgpack';

class WebSocketWrapper {
  static instances = {};
  listeners = [];
  retryCount = 0;
  maxRetries = 2;

  constructor(port, comopnent_id, spinner = false) {
    this.ip = window.location.hostname;
    this.port = port;
    this.comopnent_id = comopnent_id;
    this.spinner = spinner;
    this.pendingMessages = [];
    this.creation_time = Date.now();
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
        this.ws.close();
        this.retryConnection();
      }
    }, 15000);  // Reduced timeout to 15 seconds

    this.ws.onopen = (event) => {
      clearTimeout(connectionTimeout); // Clearing the timeout once connected
      this.retryCount = 0; // Reset retry count on successful connection
      const delay = Date.now() - this.creation_time;
      console.log(`Connection opened after ${delay} miliseconds from initial constructor`);
      this.sendPendingMessages(); // Send any messages that were queued
    };

    this.ws.onerror = (error) => {
      clearTimeout(connectionTimeout); // Clearing the timeout on error
      console.log("WebSocket Error:", error);
      this.cleanup();  // Custom method to clean up state
      this.retryConnection();
    };

    this.ws.onclose = (event) => {
      console.log("Connection closed:", event);
      this.cleanup();  // Custom method to clean up state
      this.retryConnection();
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

  retryConnection() {
    if (this.retryCount < this.maxRetries) {
      this.retryCount++;
      console.log(`Retrying connection (${this.retryCount}/${this.maxRetries})...`);
      setTimeout(() => {
        this.connect();
      }, 1000);  // Retry after 1 second
    } else {
      console.error("Max retries reached. Unable to connect to WebSocket.");
    }
  }

  cleanup() {
    if (this.ws) {
      this.ws.onopen = this.ws.onclose = this.ws.onerror = this.ws.onmessage = null;
      this.ws = null;
    }
  }

  sendPendingMessages() {
    while (this.pendingMessages.length > 0) {
      const message = this.pendingMessages.shift();
      this.ws.send(message);
      const send_time = Date.now();
      const overall_delay = send_time - this.creation_time;
      console.log(`Pending message sent to server: ${send_time}, ${message}, overall delay from constructor: ${overall_delay}`);
    }
  }

  sendData(data) {
    if (this.spinner) {
      this.showSpinner();
    }

    try {
       const accessToken = JSON.parse(localStorage.getItem('b97174ee-38fc-46e6-ac06-c013ee14a825'))['accessToken']
       console.log(accessToken , 'accessToken')
       new_data['accessToken'] = accessToken
    }catch (e){
      console.log('not login')
    }
    const jsonString = JSON.stringify(new_data);

    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(jsonString);
      console.log("Data sent to server:", jsonString);
    } else if (this.ws.readyState === WebSocket.CONNECTING) {
      console.warn("WebSocket connection is opening, queuing message", this.comopnent_id, Date.now());
      this.pendingMessages.push(jsonString); // Queue the message
    } else {
      console.error("WebSocket connection is closed, reconnecting and queuing message");
      this.pendingMessages.push(jsonString); // Queue the message
      this.connect();
    }
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
