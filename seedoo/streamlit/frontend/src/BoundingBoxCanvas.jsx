import React, { Component } from 'react';

class BoundingBoxCanvas extends Component {
    state = {
        drawing: false,
        startX: 0,
        startY: 0,
        endX: 0,
        endY: 0,
        boundingBoxes: [],
        selectedBoxIndex: null,
        resizingBox: false,
        resizingAnchor: null, // NEW: Will specify which anchor is being resized for clarity
    };

    canvasRef = React.createRef();
    componentDidMount() {
        // Ensure canvas size to be at least 300x300
        const canvas = this.canvasRef.current;
        canvas.width = Math.max(300, canvas.width);
        canvas.height = Math.max(300, canvas.height);

        // Ensure parent container resizes to fit the canvas
        if (canvas.parentElement) {
            canvas.parentElement.style.width = `${canvas.width}px`;
            canvas.parentElement.style.height = `${canvas.height}px`;
        }
    }

    drawAnchorPoint(ctx, x, y) {
        // EXISTING: Draws red anchor points for resizing
        ctx.fillStyle = 'red';
        ctx.fillRect(x - 3, y - 3, 6, 6);
    }

    isPointOnAnchor(box, x, y) {
        // EXISTING: Checks if a clicked point is near any of the anchors for resizing
        const anchors = [
            { x: box.startX, y: box.startY, position: 'topLeft' },
            { x: box.endX, y: box.startY, position: 'topRight' },
            { x: box.startX, y: box.endY, position: 'bottomLeft' },
            { x: box.endX, y: box.endY, position: 'bottomRight' }
        ];
        const activeAnchor = anchors.find(anchor => Math.abs(anchor.x - x) <= 5 && Math.abs(anchor.y - y) <= 5);
        return activeAnchor ? activeAnchor.position : null;
    }
    getClickedBox(x, y) {
        const lineWidth = 5; // Width of the bounding box border

        // Check if a point (x,y) is close to a line segment (x0,y0)-(x1,y1)
        const isNearLine = (x, y, x0, y0, x1, y1) => {
            const d = Math.abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / Math.sqrt((y1 - y0) ** 2 + (x1 - x0) ** 2);
            return d <= lineWidth;
        };

        return this.state.boundingBoxes.findIndex(box =>
            (isNearLine(x, y, box.startX, box.startY, box.endX, box.startY) ||
             isNearLine(x, y, box.startX, box.endY, box.endX, box.endY) ||
             isNearLine(x, y, box.startX, box.startY, box.startX, box.endY) ||
             isNearLine(x, y, box.endX, box.startY, box.endX, box.endY))
        );
    }

handleMouseDown = (event) => {
    event.preventDefault();

    const rect = this.canvasRef.current.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const boxIndex = this.getClickedBox(x, y);

    // If a box's border was clicked on
    if (boxIndex !== -1) {
        this.setState({ selectedBoxIndex: boxIndex });

        // Check if we clicked on an anchor point for resizing
        if (this.isPointOnAnchor(this.state.boundingBoxes[boxIndex], x, y)) {
            this.setState({ resizingBox: true });
            return;  // Early return to prevent any drawing action while resizing
        }
    }

    // If another bounding box is selected (editing mode), don't draw a new bounding box.
    if (this.state.selectedBoxIndex !== null && boxIndex === -1) {
        this.setState({ selectedBoxIndex: null });  // Deselect the box
        return;  // Exit without drawing
    }

    // If we're currently drawing a bounding box, this will complete the drawing.
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
    } else {  // If not currently drawing and didn't click on an existing box, start drawing
        this.setState({
            drawing: true,
            startX: x,
            startY: y,
        });
    }
}

    handleMouseMove = (event) => {
        const rect = this.canvasRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        if (this.state.drawing) {
            // EXISTING: Update the ending coordinates while drawing
            this.setState({
                endX: x,
                endY: y,
            });
        }

        if (this.state.resizingBox && this.state.selectedBoxIndex !== null) {
            // NEW: Resizing logic based on the anchor being dragged
            const box = { ...this.state.boundingBoxes[this.state.selectedBoxIndex] };

            switch (this.state.resizingAnchor) {
                case 'topLeft':
                    box.startX = x;
                    box.startY = y;
                    break;
                case 'topRight':
                    box.endX = x;
                    box.startY = y;
                    break;
                case 'bottomLeft':
                    box.startX = x;
                    box.endY = y;
                    break;
                case 'bottomRight':
                    box.endX = x;
                    box.endY = y;
                    break;
                default:
                    break;
            }

            const newBoxes = [...this.state.boundingBoxes];
            newBoxes[this.state.selectedBoxIndex] = box;
            this.setState({ boundingBoxes: newBoxes });
        }
    }

    handleMouseUp = (event) => {
        if (this.state.resizingBox) {
            this.setState({ resizingBox: false, resizingAnchor: null }); // EXISTING: End resizing mode
        }
    }


    componentDidUpdate() {
        const canvas = this.canvasRef.current;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        this.state.boundingBoxes.forEach((box, index) => {
            if (index === this.state.selectedBoxIndex) {
                ctx.strokeStyle = 'red';
                ctx.lineWidth = 5;  // NEW: Make the selected bounding box border wider
            } else {
                ctx.strokeStyle = 'black';
                ctx.lineWidth = 2;  // Make the regular bounding box border a bit wider
            }
            ctx.strokeRect(box.startX, box.startY, box.endX - box.startX, box.endY - box.startY);

            if (index === this.state.selectedBoxIndex) {
                // Draw anchor points for resizing
                this.drawAnchorPoint(ctx, box.startX, box.startY);
                this.drawAnchorPoint(ctx, box.endX, box.startY);
                this.drawAnchorPoint(ctx, box.startX, box.endY);
                this.drawAnchorPoint(ctx, box.endX, box.endY);
            }
        });

        if (this.state.drawing) {
            // EXISTING: Display bounding box being drawn with dashed lines
            ctx.setLineDash([5, 3]);
            ctx.strokeRect(this.state.startX, this.state.startY, this.state.endX - this.state.startX, this.state.endY - this.state.startY);
            ctx.setLineDash([]);
        }
    }

    render() {
        return (
            // Set canvas style to be anchored to the top-left corner
            <canvas ref={this.canvasRef}
                    style={{ position: 'absolute', top: 0, left: 0, opacity: 0.7, minWidth: '300px', minHeight: '300px' }}
                    onMouseDown={this.handleMouseDown}
                    onMouseMove={this.handleMouseMove}
                    onMouseUp={this.handleMouseUp}>
            </canvas>
        );
    }
}

export default BoundingBoxCanvas;
