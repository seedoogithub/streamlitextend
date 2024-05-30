import React, { Component } from 'react';

class TaggingImage extends Component {
    state = {
        drawing: false,
        startX: 0,
        startY: 0,
        endX: 0,
        endY: 0,
        boundingBoxes: [],
        selectedBoxIndex: null, // Using index instead of the object to easily modify the right box.
        resizingBox: false,
        resizingAnchor: null, // Identify which anchor is being resized
        canvasWidth: 0,       // FIX: Track canvas dimensions
        canvasHeight: 0       // FIX: Track canvas dimensions
    };

    canvasRef = React.createRef();
    imgRef = React.createRef();  // FIX: Ref for the image to get its natural dimensions

    componentDidMount() {
        // FIX: Set canvas dimensions based on image dimensions
        const img = this.imgRef.current;
        this.setState({
            canvasWidth: img.naturalWidth,
            canvasHeight: img.naturalHeight
        });
    }

    drawAnchorPoint(ctx, x, y) {
        ctx.fillStyle = 'red';
        ctx.fillRect(x - 3, y - 3, 6, 6);
    }

    /* NEW FUNCTION: Check if the clicked point is near any of the anchors */
    isPointOnAnchor(box, x, y) {
        const anchors = [
            { x: box.startX, y: box.startY },
            { x: box.endX, y: box.startY },
            { x: box.startX, y: box.endY },
            { x: box.endX, y: box.endY }
        ];
        return anchors.some(anchor => Math.abs(anchor.x - x) <= 5 && Math.abs(anchor.y - y) <= 5);
    }
   // NEW FIX: Check if a box was clicked
    getClickedBox(x, y) {
        return this.state.boundingBoxes.findIndex(box =>
            x >= box.startX && x <= box.endX && y >= box.startY && y <= box.endY
        );
    }

    handleImageLoad = () => {
        // Once image is loaded, update canvas dimensions to match
        const img = this.imgRef.current;
        this.setState({
            canvasWidth: img.clientWidth,
            canvasHeight: img.clientHeight
        });
    }

    handleMouseDown = (event) => {
        event.preventDefault(); // FIX: Prevent image drag or text selection

        const rect = this.canvasRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // FIX: Deselect previously selected box if any box wasn't clicked
        let wasBoxClicked = false;

        // FIX: Check if a box was clicked and select it
        const boxIndex = this.getClickedBox(x, y);
        if (boxIndex !== -1) {
            this.setState({ selectedBoxIndex: boxIndex });
            wasBoxClicked = true;

            // Check if we clicked on an anchor point for resizing
            if (this.isPointOnAnchor(this.state.boundingBoxes[boxIndex], x, y)) {
                this.setState({ resizingBox: true });
                return;
            }
        }

        // Previous Code: If we're already drawing a bounding box, this will complete the drawing.
        if (this.state.drawing) {
            this.setState({
                drawing: false,
                boundingBoxes: [...this.state.boundingBoxes, {
                    startX: this.state.startX,
                    startY: this.state.startY,
                    endX: x,
                    endY: y,
                }],
            });
        } else if (!wasBoxClicked) { // FIX: Only begin drawing if we didn't click on a box
            this.setState({
                drawing: true,
                startX: x,
                startY: y,
            });
        }
    }

    handleMouseMove = (event) => {
        event.preventDefault();  // FIX: Prevent any default behavior during the mouse move

        const rect = this.canvasRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // FIX: Check and ensure the mouse move remains within image boundaries
        const clampedX = Math.max(0, Math.min(this.state.canvasWidth, x));
        const clampedY = Math.max(0, Math.min(this.state.canvasHeight, y));

        // Previous code: If we're drawing, update the ending coordinates
        if (this.state.drawing) {
            this.setState({
                endX: clampedX,
                endY: clampedY,
            });
        }

        // FIX: Handle resizing of the selected box
        if (this.state.resizingBox && this.state.selectedBoxIndex !== null) {
            const box = { ...this.state.boundingBoxes[this.state.selectedBoxIndex] };

            // This is a simplified version and might need more tweaking for a robust solution
            // Determining which corner of the bounding box is closest to the mouse pointer
            if (Math.abs(box.startX - x) <= 5) box.startX = clampedX;
            if (Math.abs(box.endX - x) <= 5) box.endX = clampedX;
            if (Math.abs(box.startY - y) <= 5) box.startY = clampedY;
            if (Math.abs(box.endY - y) <= 5) box.endY = clampedY;

            const newBoxes = [...this.state.boundingBoxes];
            newBoxes[this.state.selectedBoxIndex] = box;
            this.setState({ boundingBoxes: newBoxes });
        }
    }


    // FIX: Implement handleMouseUp for more controlled drawing
    handleMouseUp = (event) => {
        if (this.state.drawing) {
            const width = Math.abs(this.state.startX - this.state.endX);
            const height = Math.abs(this.state.startY - this.state.endY);
            if (width < 10 && height < 10) {
                // Assume it's a cancel action
                this.setState({ drawing: false });
            }
        }
    }


componentDidUpdate() {
    const canvas = this.canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw all bounding boxes
    for (const box of this.state.boundingBoxes) {
        ctx.strokeRect(box.startX, box.startY, box.endX - box.startX, box.endY - box.startY);
    }

    // If currently drawing a bounding box, display it with dashed lines
    if (this.state.drawing) {
        ctx.setLineDash([5, 3]);
        ctx.strokeRect(this.state.startX, this.state.startY, this.state.endX - this.state.startX, this.state.endY - this.state.startY);
        ctx.setLineDash([]); // Resetting back to solid lines
    }


    // Draw anchor points for the selected box
    if (this.state.selectedBoxIndex !== null) {
        const box = this.state.boundingBoxes[this.state.selectedBoxIndex];

        // FIX: Highlight the selected bounding box with a red border
        ctx.strokeStyle = 'red';
        ctx.lineWidth = 2;
        ctx.strokeRect(box.startX, box.startY, box.endX - box.startX, box.endY - box.startY);
        ctx.strokeStyle = 'black'; // Resetting stroke color
        ctx.lineWidth = 1;

        // Draw anchor points
        this.drawAnchorPoint(ctx, box.startX, box.startY);
        this.drawAnchorPoint(ctx, box.endX, box.startY);
        this.drawAnchorPoint(ctx, box.startX, box.endY);
        this.drawAnchorPoint(ctx, box.endX, box.endY);

        // FIX: Draw a delete 'X' icon at the top-right corner of the selected box
        ctx.fillStyle = 'red';
        ctx.font = '16px Arial';
        ctx.fillText("X", box.endX - 10, box.startY + 10); // Adjust positioning as needed
    }
}


    render() {
        return (
            <div style={{ position: 'relative' }}>
                <img ref={this.imgRef}
                     src={`data:image/jpeg;base64,${this.props.image}`}
                     alt=""
                     onLoad={this.handleImageLoad}  // <- Add the onLoad event handler here
                     style={{ maxWidth: '100%', display: 'block' }} />
                <canvas ref={this.canvasRef}
                        width={this.state.canvasWidth}
                        height={this.state.canvasHeight}
                        style={{ position: 'absolute', top: 0, left: 0 }}
                        onMouseDown={this.handleMouseDown}
                        onMouseMove={this.handleMouseMove}
                        onMouseUp={this.handleMouseUp}>
                </canvas>
            </div>
        );
    }
}

export default TaggingImage;

