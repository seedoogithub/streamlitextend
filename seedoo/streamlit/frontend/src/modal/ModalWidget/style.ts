import styled from "styled-components";

export const WrappeeSubSlider = styled.div`
  height: 100%;
   border: 1px solid rgba(250, 250, 250, 0.2);
  .button_animate:active {
    transform: scale(1.1);
    background-color: #ddd;
  }

  .closeModal {
    position: absolute;
    right: 10px;
    top: 5px;
    z-index: 1000;
    cursor: pointer;
    color: white;
    text-align: center;
    user-select: none;
    background-color: rgb(19, 23, 32);
    border-radius: 6px;
    border: 1px solid rgba(250, 250, 250, 0.2);
  }

  .closeModal:hover {
    border-color: rgb(255, 75, 75);
    color: rgb(255, 75, 75);
  }

  select {
    border: none;
    color: rgb(102, 102, 102);
  }

  input {
    border: none;
    color: rgb(102, 102, 102);
  }

  .wrapper_button {
    width: 120px;
    height: 30px;

    > div {
      width: 100%;
      height: 100%;

      button {
        background: transparent !important;
        border: 1.5px solid #29e0e6 !important;
        border-radius: 9px;
        transition: all 0.3s ease;

        span {
          color: #29e0e6 !important;
        }
      }
    }
  }

  .wrapper_tabs {
    background: #f6f6f6;
    display: flex;

    .select_layout {
      select {
        width: 100px;
        margin: 3px;
        margin-left: 6px;
        margin-right: 10px;
      }
    }

    .tab {
      padding: 3px 10px 3px 10px;
      cursor: pointer;
      position: relative;

      .warnings_length {
        position: absolute;
        right: -5px;
        top: -5px;
        font-size: 10px;
        width: 15px;
        height: 15px;
        border-radius: 50%;
        background: red;
        display: flex;
        align-items: center;
        justify-content: center;
        color: black;
      }
    }

    .active_tab {
      background: #cdcaca;
    }
  }

  //.wrapper_show_similar:hover {
  //  z-index: 222;
  //}
  .wrapper_show_similar {
    border-radius: 36px;
    overflow: hidden;
  }

  .show_similar_centre {
    position: absolute;
    top: 0;
    height: 35px;
    width: 85px;
    left: 50%;
    transform: translateX(-50%);
    transition: all 0.5s ease 0s;
    background-color: rgb(41, 224, 230);
    display: flex;
    -webkit-box-pack: center;
    justify-content: center;
    -webkit-box-align: center;
    align-items: center;
    font-size: 22px;
    border-radius: 0px 0px 10px 10px;
    cursor: pointer;
    z-index: 1;
  }


  .getSimilar {
    position: absolute;
    top: 0;
    height: 35px;
    width: 85px;
    right: 20px;

    transition: all 0.5s ease 0s;
    background-color: rgb(41, 224, 230);
    display: flex;
    -webkit-box-pack: center;
    justify-content: center;
    -webkit-box-align: center;
    align-items: center;
    font-size: 22px;
    border-radius: 0px 0px 10px 10px;
    cursor: pointer;
    z-index: 1;
  }

  .show_similar {
    position: absolute;
    top: 0;
    height: 35px;
    width: 85px;
    left: 20px;

    transition: all 0.5s ease 0s;
    background-color: rgb(41, 224, 230);
    display: flex;
    -webkit-box-pack: center;
    justify-content: center;
    -webkit-box-align: center;
    align-items: center;
    font-size: 22px;
    border-radius: 0px 0px 10px 10px;
    cursor: pointer;
    z-index: 1;
  }

  .main_item {
    background-color: rgb(230 141 41);
  }

  .show_hide_button {
    position: absolute;
    top: 0;
    height: 35px;
    width: 85px;
    left: 20px;
    color: #1b1e21;
    transition: all 0.5s ease 0s;
    background-color: rgb(249, 250, 250);
    display: flex;
    -webkit-box-pack: center;
    justify-content: center;
    -webkit-box-align: center;
    align-items: center;
    font-size: 22px;
    border-radius: 0px 0px 10px 10px;
    cursor: pointer;
    z-index: 1;
  }

  .wrapper_body_sub {
    display: flex;

    .wrapper_item_body {
      width: 12.5%;

      .wrapper_item {
        height: 300px;
        border: 2px solid rgb(246 246 246);
        position: relative;
        padding-top: 35px;

        .hide_one_elem {
          position: absolute;
          right: 10px;
          bottom: 10px;
          z-index: 20;
          background-color: white;
          color: #1b1e21;
          font-size: 30px;
          padding: 5px 10px;
          cursor: pointer;
        }

        .wrapper_image_childe {
          position: absolute;
          left: 0;
          top: 0;
          height: 300px;
          top: 35px;
          width: 100%;
        }
      }

      .is_not_equal {
        position: absolute;
        inset: 0px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #e35353;
        font-size: 50px;
        top: 225px;

        .is_equal_spec {
          color: green;
        }
      }

      .is_equal {
        position: absolute;
        inset: 0px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: green;
        font-size: 50px;
      }
    }

    img {
      //width: 100%;
      //height: 300px;
      //object-fit: contain;
    }
  }

  .wrapepr_tree_bottom {
    display: flex;
    max-height: 570px;
    overflow: auto;
    overflow-x: hidden;
    width: 300px;

    .wrapper_item_tree_bottom {
      width: 12.5%;

      .border_tree {
        border: 2px solid rgb(246 246 246);
        position: relative;

        .main_wrapper_tree {
          display: flex;
          flex-direction: column;
        }

        .clear {
          position: absolute;
          right: 8px;
          top: 5px;
          z-index: 10;
          background: white;
          padding: 2px;
          font-size: 20px;
          cursor: pointer;
          font-family: Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
        }
      }
    }
  }

  .wrapepr_tree_bottom::-webkit-scrollbar {
    width: 9px;
  }

  .wrapepr_tree_bottom::-webkit-scrollbar-thumb {
    background-color: #888;
    border-radius: 6px;
  }

  .wrapepr_tree_bottom::-webkit-scrollbar-track {
    background-color: #eee;
  }

  .wrapepr_button_resolve {
    display: flex;

    .wrapper_button {
      margin-left: 10px;
    }
  }

  .wrapper_for_absolute {
    position: relative;
    width: 100%;
    height: 100vh;
    overflow: hidden;

    .wrapper_item_body {
      width: 300px;
    }

    .wrapper_item_tree_bottom {
      width: 100%;
    }
  }

  .hideButton {

    right: 40px;
    color: #1b1e21;
    top: 5px;
    padding: 0px 4px 0 4px;
    cursor: pointer;
    background: white;
    border: 1px solid #acacac;
    z-index: 100;
    width: 35px;
    text-align: center;
  }

  .hideButtonAll {
    display: block;
    padding: 0.25rem 0.75rem;
    border-radius: 0.5rem;
    margin-top: 10px;
    color: inherit;
    text-align: center;
    user-select: none;
    background-color: rgb(19, 23, 32);
    cursor: pointer;
    border: 1px solid rgba(250, 250, 250, 0.2);
  }

  .hideButtonAll:hover {
    border-color: rgb(255, 75, 75);
    color: rgb(255, 75, 75);
  }

  .saveButton:hover {
    border-color: rgb(255, 75, 75);
    color: rgb(255, 75, 75);
  }

  .saveButton {
    position: absolute;
    right: 37px;
    font-family: 'Source Sans 3';
    line-height: 1.13;
    top: 5px;
    width: 45px;
    cursor: pointer;
    z-index: 100;
    text-align: center;
    padding: 0rem 0.4rem;
    border-radius: 0.4rem;
    color: inherit;
    user-select: none;
    background-color: rgb(19, 23, 32);
    border: 1px solid rgba(250, 250, 250, 0.2);

    span {
      color: green;
      font-size: 13px;
    }
  }

  .advanced_menu {
    position: absolute;
    top: 5px;
    background: #0e1117;
    padding: 4px;
    padding-top: 0;
    border-radius: 7px;
    transition: 1s all;
    right: 103px;
    height: 14px;
    z-index: 100003;
    overflow: hidden;
    border: 1px solid rgba(250, 250, 250, 0.2);
    font-family: 'Source Sans 3', sans-serif;
    

    .checkbox_stile {
      margin-top: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;

      .checkbox-input {
        appearance: none;
        -webkit-appearance: none;
        -moz-appearance: none;
        width: 16px;
        height: 16px;
        border: 2px solid rgba(250, 250, 250, 0.4);;
        border-radius: 4px;
        outline: none;
        cursor: pointer;
        margin-right: 10px;
        position: relative;
      }

      .checkbox-input:checked {
        background-color: rgb(255, 75, 75); /* Orange background when checked */
        border: 2px solid rgb(255, 75, 75);
      }

      .checkbox-input:checked::before {
        content: '\\2713'; /* Unicode character for checkmark */
        display: block;
        width: 16px;
        height: 14px;
        text-align: center;
        line-height: 16px;
        color: #fff;
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
      }
    }

    .title {
      display: flex;

      .text_title {
        width: 100%;
        text-align: center;
        cursor: pointer;
        line-height: 1.12;
      }

      .arrow {
        transition: 0.5s all;
        position: absolute;
        right: 5px;
        top: -5px;
      }

      .rotate {
        transition: 0.5s all;
        transform: rotate(180deg);
        position: absolute;
        right: 5px;
        top: 1px;
      }
    }

    .title:hover {
      .text_title {
        color: rgb(255, 75, 75);
      }

      .arrow {
        color: rgb(255, 75, 75);
      }

      .rotate {
        color: rgb(255, 75, 75);
      }
    }

    .slider_component {
      margin-top: 24px;
      width: 192px;
    }

    .slider_component_bottom {
      display: flex;
      justify-content: space-between;
      color: white;
      padding: 0px 7px;

      span {
        font-size: 13px;
      }
    }
  }

  .advanced_menu_height {
    height: 285px;
  }

  .filterWarnings {
    right: 238px;
    color: #1b1e21;
    top: 5px;
    padding: 0px 4px 0 4px;
    cursor: pointer;
    background: white;
    border: 1px solid #acacac;
    z-index: 100;
    text-align: center;
  }

  .filterButton {
    right: 238px;
    color: #1b1e21;
    text-align: center;
    top: 5px;
    padding: 0px 4px 0 4px;
    cursor: pointer;
    background: white;
    border: 1px solid #acacac;
    z-index: 100;
  }

  .filterSelect {
    color: #1b1e21;
    right: 334px;
    text-align: center;
    top: 5px;
    margin-top: 10px;
    padding: 0px 4px 0 4px;
    cursor: pointer;
    border-radius: 5px;
    border: 1px solid #585858;
    z-index: 100;

    select {
      width: 100%;
      font-family: sans-serif;
      font-size: 15px;
      background: black;
      outline: none;
      color: white;
      padding: 4px;
    }
  }

  .wrapper_tree {
    color: rgba(0, 0, 0, 0.70);

    .wrapper_title {
      display: flex;
      transition: 1s all;
      transform: translate(2px, 0px);

      .icon {
        display: flex;
        justify-content: center;
        align-items: center;
        cursor: pointer;
        padding-top: 4px;
      }

      .right {
        svg {
          transform: rotate(-90deg);
        }
      }

      .title_tree {
        margin-left: 12px;
        font-size: 22px;
        display: flex;
        align-items: center;
        line-height: 21px;
        margin-bottom: 5px;
        margin-top: 5px;
        font-family: Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';

        .icon_ok {
          display: block;
          width: 35px;
          margin-left: 2px;
          cursor: pointer;
        }

        input {
          width: 17px;
          height: 17px;
          margin-left: 10px;
          margin-top: 8px;
          cursor: pointer;
        }
      }
    }

    .item_tree {
      padding-left: 40px;
      display: flex;
      font-size: 22px;
      line-height: 21px;
      margin-bottom: 6px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';

      .input {
        margin-right: 10px;

        input {
          height: 17px;
          width: 17px;
          cursor: pointer;
        }
      }
    }
  }
`;
export const Preloader = styled.div`
  .first_spinner {
    border: 4px solid rgba(255, 255, 255, 0.9);
    border-radius: 50%;
    border-top: 4px solid #29e0e6;
    width: 20px;
    height: 20px;
    animation: spin 1s linear infinite;
    position: absolute;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10000;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }
`;
export const Preloader2 = styled.div`
  position: relative;

  .preloader {
    position: absolute;
    top: 50%;
    left: 50%;
    /* inset: 32px 0px 0px 50%; */
    transform: translate(-50%, -50%);
    width: 20px;
    height: 18px;
    z-index: 9999;
  }

  .spinner {
    margin: 0px auto;
    width: 20px;
    height: 20px;
    position: relative;
  }

  .spinner:before {
    content: "";
    display: block;
    padding-top: 100%;
  }

  .spinner:after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 60%;
    height: 60%;
    border-radius: 50%;
    border: 3px solid #3498db;
    border-top-color: #fff;
    animation: spinner 1s linear infinite;
  }

  @keyframes spinner {
    0% {
      transform: rotate(0);
    }
    100% {
      transform: rotate(360deg);
    }
  }
`;
export const WrapperComponent = styled.div`
  height: calc(100% - 20px);
  color: rgb(102, 102, 102);
  padding-top: 20px;
  padding-left: 10px;
  padding-right: 10px;

  .wrapper_header {
    display: flex;
    height: calc(10% - 26px);

    .title {
      width: 24%;
      padding: 10px;
      background: white;
      display: flex;
      justify-content: center;
      align-items: center;
      box-shadow: 0 0 10px -1px rgb(0 0 0 / 10%);
      border-radius: 10px;
      margin-right: 10px;
      color: rgb(102, 102, 102);
      font-weight: normal;
      font-size: 24px;
    }

    .wrapper_date {
      display: flex;
      width: 90%;
      background: white;
      padding: 10px;
      box-shadow: 0 0 10px -1px rgb(0 0 0 / 10%);
      border-radius: 10px;
      justify-content: space-between;
      align-items: center;

      .wrapper_date_select {
        display: flex;

        .start_date {
          margin-right: 10px;
        }

        .end_date {
          margin-left: 10px;
          margin-right: 10px;
        }

        .bp3-control-group {
          margin-right: 10px;
        }

        label {
          margin-right: 5px;
          color: rgb(102, 102, 102);
          font-size: 14px;
          font-weight: normal;
          font-style: normal;
        }
      }

      .wrapper_button {
        width: 120px;
        height: 30px;

        button {
          width: 100%;
          height: 100%;
          background: transparent !important;
          border: 1.5px solid #29e0e6 !important;
          border-radius: 9px;
          cursor: pointer;
          transition: all 0.3s ease;
          color: rgb(41, 224, 230);
          font-weight: 600;
        }
      }
    }
  }

  .wrapper_body {
    height: calc(90% - 30px);
    box-shadow: 0 0 10px -1px rgb(0 0 0 / 10%);
    border-radius: 10px;
    background: white;
    margin-top: 30px;
    padding: 10px;
    position: relative;
    overflow: hidden;

    .header_corusel {
      position: absolute;
      top: -50px;
      height: 20px;
      width: 10%;
      left: 50%;
      transform: translateX(-50%);
      transition: all 1s;
      background-color: #29e0e6;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 14px;
      border-radius: 0px 0px 10px 10px;
      cursor: pointer;
    }

    .header_corusel_show {
      position: absolute;
      top: 0px;
      height: 20px;
      z-index: 1;
      width: 10%;
      left: 50%;
      transform: translateX(-50%);
      transition: all 1s;
      background-color: #29e0e6;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 14px;
      border-radius: 0px 0px 10px 10px;
      cursor: pointer;
    }

    .header_corusel:hover {
      top: 0px;
    }

    .wrapper_carusel:hover + .header_corusel {
      top: 0px;
    }

    .wrapper_attention {
      display: flex;

      .title {
        margin-right: 10px;
        font-size: 18px;
      }

      .slider {
        width: 100%;
        display: flex;
        align-items: center;

        > div {
          width: 100%;
        }
      }
    }

    .wrapper_carusel {
      margin-bottom: 50px;
      height: calc(26% - 50px);

      .wrapper_carusel_button {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-top: 10px;

        button {
          border-radius: 9px;
          transition: all 0.3s ease 0s;
          padding: 0px 10px;
          background: transparent !important;
          border: 1.5px solid rgb(41, 224, 230) !important;
          color: #26e0e6 !important;
          padding: 6px 42px !important;
        }
      }

      .page_number_item {
        margin-left: 6px;
        margin-right: 6px;
      }

      .pagination {
        justify-content: center;
        align-items: center;
        display: flex;

        button {
          background: transparent !important;
          border: none !important;
          border-radius: 9px;
          transition: all 0.3s ease;
          padding: 0px 10px;
          color: #26e0e6 !important;
          padding: 2px 42px !important;
          cursor: pointer;
          box-shadow: inset 0 0 0 1px rgba(16, 22, 26, .2), inset 0 -1px 0 rgba(16, 22, 26, .1);
          padding: 9px 10px !important;
          border: none !important;

          span {
            fill: #29e0e6 !important;
            justify-content: center;
            align-items: center;
            display: flex;
          }
        }

        button[disabled=disabled], button:disabled {
          border: none !important;
          cursor: not-allowed;
          box-shadow: none;
        }
      }

      button {
        background: transparent !important;
        border: 1.5px solid #29e0e6 !important;
        border-radius: 9px;
        transition: all 0.3s ease;
        padding: 0px 10px;
        color: #26e0e6 !important;
        padding: 6px 42px !important;
        cursor: pointer;

        span {
          fill: #29e0e6 !important;
        }
      }

      button[disabled=disabled], button:disabled {
        border: none !important;
        cursor: not-allowed;
      }

      .carusel {
        height: 100%;
        box-shadow: 0 0 10px -1px rgb(0 0 0 / 10%);
        border-radius: 10px;
        background: white;
        overflow: hidden;
        display: flex;

        img {
          width: 9.33%;
        }
      }
    }

    .wrapper_carusel_hide {
      margin-bottom: 0;
      height: 0;
      overflow: hidden;
    }

    .wrapper_body_img {
      display: flex;
      height: 74%;
      overflow: auto;

      img {
        width: 100%;
        height: 200px;
        object-fit: contain;
      }
      
      .wrapper_tree {
        width: calc(38% - 10px);
        overflow: auto;
        margin-right: 10px;
        box-shadow: 0 0 10px -1px rgb(0 0 0 / 10%);
        border-radius: 10px;
        background: white;
        padding: 10px;

        .tree {
          display: flex;
          justify-content: space-evenly;
        }
      }
    }
  }

  .wrapper_body_modal {
    height: 100%;
    margin-top: 0;
  }
`;
//finish