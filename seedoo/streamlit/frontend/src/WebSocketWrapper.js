import * as msgpack from '@msgpack/msgpack';
let start
class WebSocketWrapper {
  static instances = {};
  listeners = [];

  constructor(port, comopnent_id , spinner = false) {
    this.ip = window.location.hostname;
    this.port = port;
    this.comopnent_id = comopnent_id;
    this.connect();
    this.spinner = spinner;
  }

  static getInstance(port, comopnent_id , spinner = false) {
    const key = `${port}:${comopnent_id}`;
    console.log('Getting key: ', key);
    if (!WebSocketWrapper.instances[key]) {
      WebSocketWrapper.instances[key] = new WebSocketWrapper(port, comopnent_id , spinner);
    }

    return WebSocketWrapper.instances[key];
  }
  hideSpinner() {
      if(this.spinner) {
           const spinner = document.querySelector('.spinner_custom');
            if(spinner) {
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
    if(window.location.protocol !== "https:"){
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
  }, 15000);

  this.ws.onopen = (event) => {
    clearTimeout(connectionTimeout); // Clearing the timeout once connected
    console.log("Connection opened:", event);
  };

  this.ws.onerror = (error) => {
    clearTimeout(connectionTimeout); // Clearing the timeout on error
    console.log("WebSocket Error:", error);
  };

  this.ws.onclose = (event) => {
    console.log("Connection closed:", event);
    setTimeout(()=>{
      this.connect();
    },1000)
  };

  this.ws.onmessage = (event) => {
    console.log('Got message');
    this.hideSpinner();
    console.log(event);
    // let jsonString = event.data;
    // jsonString = jsonString.replace(/NaN/g, 'null');

    if (typeof event.data === 'string') {
      const message = JSON.parse(event.data);
      // console.log(`time: ${(Date.now() -start)/1000} s`)
        this.listeners.forEach(listener => listener(message));
    } else {
        const data = msgpack.decode(new Uint8Array(event.data));
        // console.log(`time: ${(Date.now() -start)/1000} s`)
        this.listeners.forEach(listener => listener(data));
    }

  };
}


  sendData(data) {
    const new_data = {...data}
    if(this.spinner){
       this.showSpinner()
    }
    try {
       const accessToken = JSON.parse(localStorage.getItem('b97174ee-38fc-46e6-ac06-c013ee14a825'))['accessToken']
       console.log(accessToken , 'accessToken')
       new_data['accessToken'] = accessToken
    }catch (e){
      console.log('not login')
    }

    const sendWhenReady = () => {
      if (this.ws.readyState === WebSocket.OPEN) {
          const jsonString = JSON.stringify(new_data);
          this.ws.send(jsonString);
          console.log("Data sent to server with token:", jsonString);
        // start = Date.now()

      } else if (this.ws.readyState === WebSocket.CONNECTING) {
        console.warn("WebSocket connection is opening", this.comopnent_id);

        // If WebSocket is still connecting, wait and then try again
        setTimeout(sendWhenReady, 5000);
      } else {
        console.error("WebSocket connection is closed, reconnecting");
        this.connect();
      }
    };

    sendWhenReady();

  }

  addListener(listener) {
    this.sendData({'id' : this.comopnent_id});
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
