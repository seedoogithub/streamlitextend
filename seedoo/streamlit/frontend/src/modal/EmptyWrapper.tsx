import { Empty } from "antd";
import React from "react";
import styled from "styled-components";

const Wrapper = styled.div`
  overflow: auto;
  height: 100%;

  .ant-empty {
    display: flex;
    flex-direction: column;
    justify-content: center;
    height: 100%;
    margin: 0;
  }
`;

function EmptyWrapper() {
  return (
    <Wrapper>
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
    </Wrapper>
  );
}

export default EmptyWrapper;
