import {
  Streamlit,
  StreamlitComponentBase,
  withStreamlitConnection,
} from "streamlit-component-lib";
import React from "react";
import WebSocketWrapper from '../WebSocketWrapper';
import '../global_styles.css';

interface State {
  id: string;
  clicked: boolean;
  spinner: boolean;
}

class WebsocketButton extends StreamlitComponentBase<State> {
  public state = {
    id: this.props.args['id'],
    clicked: false ,
    spinner:false
  };

  private wsWrapper: WebSocketWrapper | null = null;


  public componentDidMount(): void {
    Streamlit.setComponentReady();
    if (this.wsWrapper === null) {
      this.wsWrapper = WebSocketWrapper.getInstance(this.props.args['port'], this.props.args['id']);
      console.log('wsWrapper is null');
    }
  }


  private handleClick = (): void => {
    const newState = { ...this.state, clicked: true  ,spinner:true};
    this.setState(newState);

    if (this.wsWrapper != null) {
        console.log(newState , 'newState')
      this.wsWrapper.sendData(newState);
    }
    this.setState({ ...this.state ,spinner:false});
  };

  public render = (): React.ReactNode => {
    return (
            <button
              onClick={this.handleClick}
              className="button_animate"
              style={{
                transition: 'all 0.3s ease',
                width: 'auto', // Streamlit buttons only expand as needed
                padding: '6px 12px', // Similar padding for a balanced appearance
                textAlign: 'center', // Centers the text
                fontSize: '1rem', // Sets a readable font size, typically 16px
                fontWeight: 'bold', // Streamlit buttons use bold text
                border: 'none', // No visible border in dark mode
                backgroundColor: '#0D1017', // Specific Streamlit dark mode background color
                color: '#E1E1E1', // Light grey text color for contrast
                cursor: 'pointer', // Cursor changes on hover
                borderRadius: '0.375rem', // 6px border-radius for slight rounding
                display: 'inline-flex', // Flex to center content (text and possible icons)
                alignItems: 'center', // Vertical alignment to center
                justifyContent: 'center', // Horizontal alignment to center
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24)', // Subtle shadow for depth
                outline: 'none', // Removes the outline on focus (for aesthetics)
                userSelect: 'none', // Prevent text selection
                touchAction: 'manipulation', // Optimize the button for touch devices
              }}
            >
          {this.state.spinner ? <div className="spinner"></div> : this.props.args['label']}
      </button>
    );
  }

}

export default withStreamlitConnection(WebsocketButton)
