import React, {useState, useCallback, useEffect, useRef} from "react";
import {
    withStreamlitConnection, Streamlit
} from "streamlit-component-lib"

import styled from "styled-components";

import {Preloader, WrappeeSubSlider} from './style';
import WebSocketWrapper from '../../WebSocketWrapper';
import '../../global_styles.css';


function ModalComponent(props: AttributesComponentProps) {

    const [showModal, setShowModal] = useState(false);
    const [value, setValue] = useState('');


    useEffect(() => {
        const NewwsWrapper = WebSocketWrapper.getInstance(props.args['port'], props.args['id'], true);
        if (NewwsWrapper != null) {
            NewwsWrapper.addListener((msg: any) => {
                if (msg.event == 'similar') {

                    if (msg.showModal) {
                        setShowModal(true)
                    }
                    if(msg.value_one){
                        setValue(msg.value_one)
                    }
                }
            });
        }
    }, [])

    useEffect(() => {
        const iframe = window.frameElement as HTMLElement;
        iframe.style.visibility = "hidden";
    }, []);
    useEffect(() => {
        if (showModal) {
            const iframe = window.frameElement as HTMLElement;
            iframe.style.visibility = "visible";
            iframe.style.position = "fixed";
            iframe.style.backgroundColor = "rgba(255,255,255,0.15)";
            iframe.style.top = "50%";
            iframe.style.left = "50%";
            iframe.style.transform = "translate(-50%, -50%)";
            iframe.style.zIndex = "10000000";
            iframe.style.display = "flex";
            iframe.style.borderRadius = "10px";
            iframe.style.overflow = "hidden";
            iframe.style.width = '90%';
            iframe.style.height = '96%';
            iframe.style.border = '2px solid rgba(250, 250, 250, 0.5)'
            document.body.style.margin = '0';
        } else {
            const iframe = window.frameElement as HTMLElement;
            iframe.style.visibility = "hidden";
        }
    }, [showModal]);


    const handleModalClose = () => {
        setShowModal(false);
    }


    return (
        <WrappeeSubSlider style={{position: "relative"}}>


            <button className="closeModal" onClick={handleModalClose}>x</button>
            <div style={{
                margin: 'auto',
                fontSize: '25px',
                textAlign: 'center',
            }}>  {value}</div>


        </WrappeeSubSlider>
    );
}

export interface AttributesComponentProps {
    args: any
}

export default withStreamlitConnection(ModalComponent);



