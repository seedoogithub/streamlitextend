import * as msgpack from '@msgpack/msgpack';
import { Mutex } from 'async-mutex';

class WebSocketWrapper {
  static instances = {};
  listeners = [];
  retryCount = 0;
  maxRetries = 2;
  spinner = null; // Spinner element instance
  spinnerVisible = false; // Track spinner visibility
  spinnerQueue = [];
  spinnerMutex = new Mutex(); // Mutex for managing spinner queue

  constructor(port, component_id, spinner = false) {
    this.ip = window.location.hostname;
    this.port = port;
    this.component_id = component_id;
    this.spinnerEnabled = spinner;
    this.pendingMessages = [];
    this.creation_time = Date.now();
    this.createSpinner(); // Create spinner instance
    this.connect();
  }

  static getInstance(port, component_id, spinner = false) {
    const key = `${port}:${component_id}`;
    console.log('Getting key:', key);
    if (!WebSocketWrapper.instances[key]) {
      WebSocketWrapper.instances[key] = new WebSocketWrapper(port, component_id, spinner);
    } else {
      WebSocketWrapper.instances[key].cleanup();
      WebSocketWrapper.instances[key].connect();
    }

    return WebSocketWrapper.instances[key];
  }

  createSpinner() {
    try {
      this.spinner = document.createElement('div');
      this.spinner.className = 'spinner_custom';
      this.spinner.style.display = 'none'; // Initially hidden
      document.body.appendChild(this.spinner);
      console.log('Spinner created.');
    } catch (error) {
      console.error('Error while creating spinner:', error);
    }
  }

  hideSpinner() {
    try {
      if (this.spinner && this.spinnerVisible) {
        this.spinner.style.display = 'none';
        this.spinnerVisible = false;
        console.log('Spinner hidden.');
      } else {
        console.warn('Spinner instance not found or already hidden.');
      }
    } catch (error) {
      console.error('Error while hiding spinner:', error);
    }
  }

  showSpinner() {
    try {
      if (this.spinner && !this.spinnerVisible) {
        this.spinner.style.display = 'block';
        this.spinnerVisible = true;
        console.log('Spinner shown.');
      } else {
        console.warn('Spinner instance not found or already visible.');
      }
    } catch (error) {
      console.error('Error while showing spinner:', error);
    }
  }

  async manageSpinnerQueue() {
    const release = await this.spinnerMutex.acquire(); // Acquire the mutex lock
    try {
      if (this.spinnerQueue.length > 0) {
        const action = this.spinnerQueue.shift();
        if (action === 'open') {
          this.showSpinner();
        } else if (action === 'close') {
          this.hideSpinner();
        }
      }
    } catch (error) {
      console.error('Spinner Queue Error:', error);
    } finally {
      release(); // Release the mutex lock
      if (this.spinnerQueue.length > 0) {
        setTimeout(() => this.manageSpinnerQueue(), 100); // Check the queue again after a short delay
      }
    }
  }

  queueSpinnerAction(type) {
    this.spinnerQueue.push(type);
    if (this.spinnerQueue.length === 1) {
      this.manageSpinnerQueue(); // Start managing the queue if it's the first action
    }
  }

  connect() {
    let wsType = 'wss';
    if (window.location.protocol !== "https:") {
      wsType = 'ws';
    }
    this.ws = new WebSocket(`${wsType}://${this.ip}:${this.port}/ws/${this.component_id}`);
    this.ws.binaryType = 'arraybuffer';

    if (this.spinnerEnabled) {
      this.queueSpinnerAction('open');
    }

    // Setting up a timeout for the initial connection
    const connectionTimeout = setTimeout(() => {
      if (this.ws.readyState !== WebSocket.OPEN) {
        console.error('Connection timed out after 15 seconds.');
        this.ws.close();
        this.retryConnection();
      }
    }, 15000);  // Timeout set to 15 seconds

    this.ws.onopen = (event) => {
      clearTimeout(connectionTimeout); // Clearing the timeout once connected
      this.retryCount = 0; // Reset retry count on successful connection
      const delay = Date.now() - this.creation_time;
      console.log(`Connection opened after ${delay} milliseconds from initial constructor`);
      this.sendPendingMessages(); // Send any messages that were queued
      if (this.spinnerEnabled) {
        this.queueSpinnerAction('close'); // Close the spinner for connection success
      }
    };

    this.ws.onerror = (error) => {
      clearTimeout(connectionTimeout); // Clearing the timeout on error
      console.log('WebSocket Error:', error);
      this.cleanup();  // Custom method to clean up state
      this.retryConnection();
      if (this.spinnerEnabled) {
        this.queueSpinnerAction('close'); // Close the spinner for connection error
      }
    };

    this.ws.onclose = (event) => {
      console.log('Connection closed:', event);
      this.cleanup();  // Custom method to clean up state
      this.retryConnection();
      if (this.spinnerEnabled) {
        this.queueSpinnerAction('close'); // Close the spinner for connection close
      }
    };

    this.ws.onmessage = (event) => {
      console.log('Got message');
      if (this.spinnerEnabled) {
        this.queueSpinnerAction('close'); // Close the spinner for message receive
      }
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
      console.error('Max retries reached. Unable to connect to WebSocket.');
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
    if (this.spinnerEnabled) {
      this.queueSpinnerAction('open');
    }
      const new_data = {...data}
    try {
       const accessToken = JSON.parse(localStorage.getItem('02dba183-14e1-4c8f-837a-a0a1a75bf811'))['accessToken']
       console.log(accessToken , 'accessToken')
       new_data['accessToken'] = accessToken
    }catch (e){
      console.log('not login')
    }
    const jsonString = JSON.stringify(data);

    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(jsonString);
      console.log('Data sent to server:', jsonString);
    } else if (this.ws.readyState === WebSocket.CONNECTING) {
      console.warn('WebSocket connection is opening, queuing message', this.component_id, Date.now());
      this.pendingMessages.push(jsonString); // Queue the message
    } else {
      console.error('WebSocket connection is closed, reconnecting and queuing message');
      this.pendingMessages.push(jsonString); // Queue the message
      this.connect();
    }
  }

  addListener(listener) {
    this.sendData({ 'id': this.component_id });
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