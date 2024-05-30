import React, { Component } from 'react';
import './global_styles.css';
import TaggingImage from './TaggingImage';
import BoundingBoxCanvas from "./BoundingBoxCanvas";

class ImageCarousel extends Component {
  constructor(props) {
    try {
      super(props);
      this.thumbnailRef = React.createRef();
      this.state = {
        selectedIndex: 0,
      };
    } catch (error) {
      console.error(error);
    }
  }

  handleThumbnailClick = (index) => {
    try {
      this.setState({ selectedIndex: index });
    } catch (error) {
      console.error(error);
    }
  };

  thumbnailRef = React.createRef();

  scrollThumbnails = (direction) => {
    const container = this.thumbnailRef.current;
    const scrollAmount = 150; // width of each thumbnail, change according to your styling

    if (direction === 'left') {
      container.scrollLeft -= scrollAmount;
    } else {
      container.scrollLeft += scrollAmount;
    }
  }

  render() {
    try {
      let { data } = this.props;
      let {extra_data} = this.props;
      const selectedImage = data[this.state.selectedIndex];

      if (selectedImage == null || selectedImage == '') {
        return <div>empty</div>
      };

      if (typeof data != 'object' || data === null || !(data instanceof Array)) {
        console.warn('Data is', data)
        data = [];
      };

      return (
        <div style={{ width: '95%', height: '95%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', transform: 'scale(0.9)' }}>
          <div style={{ marginBottom: '20px', position: 'relative', display: 'flex', flexDirection: 'row' }}>
            <img
              src={`data:image/png;base64,${selectedImage.image}`}
              alt=""
              style={{ objectFit: 'contain', maxHeight: '640px', maxWidth: '480px' }}
            />
            <div style={{
              marginLeft: '20px',
              transform: 'scale(0.95)',
              borderTop: '1px solid greenyellow',
              color: 'greenyellow',
              width: '300px',
              display: 'grid',
              gridTemplateColumns: '1fr',
              rowGap: '1px',
              borderLeft: '1px solid greenyellow',
              borderRight: '1px solid greenyellow',
              overflowY: 'auto', // Add this line
              maxHeight: '400px' // Adjust this to set a maximum height
            }}>
              {Object.keys(selectedImage)
                  .filter((key) => key !== 'image')
                  .map((key) => {
                      const value = selectedImage[key];
                      const isTableData = Array.isArray(value) && value.length > 0 && typeof value[0] === 'object';

                      return (
                          <div key={key} style={{ borderBottom: '1px solid greenyellow', padding: '5px', position: 'relative' }}>
                              <strong>{key}:</strong>
                              {
                                  isTableData
                                  ? <span className="hoverable-cell">Table Data</span>
                                  : value
                              }

                              {
                                  isTableData && (
                                      <div className="hover-table">
                                          <table>
                                              <thead>
                                                  <tr>
                                                      {Object.keys(value[0]).map(header => <th key={header}>{header}</th>)}
                                                  </tr>
                                              </thead>
                                              <tbody>
                                                  {value.map((row, rowIndex) => (
                                                      <tr key={rowIndex}>
                                                          {Object.values(row).map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
                                                      </tr>
                                                  ))}
                                              </tbody>
                                          </table>
                                      </div>
                                  )
                              }
                          </div>
                      );
                  })}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <button onClick={() => this.scrollThumbnails('left')}>←</button>
              <div ref={this.thumbnailRef} style={{ display: 'flex', overflowX: 'hidden', width: '750px' }}> {/* Width adjusted for 5 thumbnails */}
                {data.map((item, index) => (
                  <img
                    key={index}
                    src={`data:image/png;base64,${item.image}`}
                    alt=""
                    style={{
                      width: '150px',
                      height: '150px',
                      cursor: 'pointer',
                      border: index === this.state.selectedIndex ? '4px solid #007BFF' : '' // Add border if selected
                    }}
                    onClick={() => this.handleThumbnailClick(index)}
                  />
                ))}
              </div>

              <button onClick={() => this.scrollThumbnails('right')}>→</button>
            </div>
          </div>
        </div>
      );
    } catch (error) {
      console.error(error);
      return <div>Error rendering Image Carousel</div>;
    }
  }
}

export default ImageCarousel;
