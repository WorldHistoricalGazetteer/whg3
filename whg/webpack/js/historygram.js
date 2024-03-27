/*
  Author: Stephen Gadd, Docuracy Ltd
  File: historygram.js
  Description: JavaScript date range visualisation and selector

  Copyright (c) 2024 Stephen Gadd
  Licensed under the Creative Commons Attribution 4.0 International License (CC-BY 4.0).
  
  Requires D3.js
*/

export default class Historygram {
    constructor(intervals, onChange = null, drawHistogram=true, addControls=true, maxBins=100, includeUndated=true, containerId='historygram') {
        this.intervals = intervals;
        this.fromValue = null;
        this.toValue = null;
        this.fromX = null;
        this.toX = null;
        this.scaleWidth = null;
		this.includeUndated = includeUndated;
		this.onChangeCallback = onChange;
        this.drawHistogram = drawHistogram;
        this.addControls = addControls;
        this.maxBins = maxBins;
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.initialise();
        this.appendUndatedCheckbox();
        this.appendStyles();
        this.initialise = this.initialise.bind(this);
        window.addEventListener('resize', this.initialise);
    }
    
    initialise() {
        d3.select(this.container).selectAll("svg").remove();
        const [binInterval, binBounds, binCounts] = this.calculateBins();
        this.histogram(binInterval, binBounds, binCounts);
    }

    calculateBins() {
        const [min, max] = this.intervals.reduce(([min, max], row) => [
            Math.min(min, ...row),
            Math.max(max, ...row)
        ], [Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]);

        const range = max - min;
        const exponent = Math.floor(Math.log10(range / this.maxBins));
        const base = [1, 2, 5].find(base => (range / (base * 10 ** exponent)) <= this.maxBins);
        const binInterval = base * 10 ** exponent;
        const adjustedMin = Math.floor(min / binInterval) * binInterval;
        const adjustedMax = Math.ceil(max / binInterval) * binInterval;
        const adjustedRange = adjustedMax - adjustedMin;
        const adjustedBinCount = Math.ceil(adjustedRange / binInterval);
        const binBounds = Array.from({ length: adjustedBinCount + 1 }, (_, i) => adjustedMin + i * binInterval);
    
        const binCounts = Array(adjustedBinCount).fill(0);
	    for (const interval of this.intervals) {
	        for (let i = 0; i < adjustedBinCount; i++) {
	            const binStart = binBounds[i];
	            const binEnd = binBounds[i + 1];
	            if (interval[0] < binEnd && interval[1] >= binStart) {
	                binCounts[i]++;
	            }
	        }
	    }
	
	    return [binInterval, binBounds, binCounts];
    }

	histogram(binInterval, binBounds, binCounts) {
	
	    // Define SVG dimensions and margins
	    const margin = { top: 10, right: 30, bottom: 30, left: 10 };
	    const width = this.container.clientWidth - margin.left - margin.right;
	    const height = this.container.clientHeight - margin.top - margin.bottom;
	
	    // Create SVG element
	    const svg = d3.select(this.container).append("svg")
	        .attr("width", width + margin.left + margin.right)
	        .attr("height", height + margin.top + margin.bottom)
	        .append("g")
	        .attr("transform", `translate(${margin.left},${margin.top})`);
	
	    // Define scales
	    const xScale = d3.scaleBand()
	        .domain(binBounds.map((_, i) => i))
	        .range([0, width])
	        .padding(0.1);
	
	    const yScale = d3.scaleLinear()
	        .domain([0, d3.max(binCounts)])
	        .nice()
	        .range([height, 0]);

		if (this.drawHistogram) {
		    // Create bars
		    svg.selectAll(".bar")
		        .data(binCounts)
		        .enter().append("rect")
		        .attr("class", "bar")
		        .attr("x", (_, i) => xScale(i) + xScale.bandwidth() / 2)
		        .attr("y", d => yScale(d))
		        .attr("width", xScale.bandwidth())
		        .attr("height", d => height - yScale(d));			
		}	
	        
		// Calculate the maximum number of labels that can be displayed without overlap
        const maxLabel = Math.max(Math.abs(binBounds[0]), Math.abs(binBounds[binBounds.length - 1]));
		const negativePrefix = binBounds[0] < 0 ? "-" : "";
		const maxLabelWidth = this.calculateTextWidth(negativePrefix + maxLabel);
		const maxLabels = Math.floor(width / (maxLabelWidth * 1.5)); // Add margin
		const labelStep = Math.ceil(binBounds.length / maxLabels);
		
		// Add x-axis with calculated label step
		svg.append("g")
		    .attr("transform", `translate(0,${height})`)
		    .call(d3.axisBottom(xScale)
		        .tickValues(xScale.domain().filter((_, i) => i % labelStep === 0))
		        .tickFormat((_, i) => binBounds[i * labelStep]));
		        
		if (this.addControls) {
			
			this.fromX = this.fromX ? this.fromX * width / this.scaleWidth : 0;
			this.toX = this.toX ? this.toX * width / this.scaleWidth : width;
						
		    // Append a group for the slider elements
	        const sliderGroup = svg.append('g')
	            .attr('class', 'range-slider');          

	        // Append bar indicating the range
	        sliderGroup.append('rect')
	            .attr('x', this.fromX)
	            .attr('y', height - 5)
	            .attr('width', this.toX - this.fromX)
	            .attr('height', 10)
	            .attr('fill', 'orange')
	            .attr('opacity', 0.3).call(d3.drag()
		            .on('start', dragStarted)
		            .on('drag', draggedBar.bind(this))
		            .on('end', dragEnded.bind(this))
		        );

	        // Append circles for slider ends
	        const circleRadius = 8;
	        sliderGroup.selectAll('circle')
	            .data([0, 1])
	            .enter().append('circle')
    			.attr('cx', (_, i) => i === 0 ? this.fromX : this.toX )
	            .attr('cy', height)
	            .attr('r', circleRadius)
	            .attr('fill', 'orange')
	            .attr('class', (_, i) => i === 0 ? 'left-handle' : 'right-handle')
	            // Add drag behavior to circles
			    .call(d3.drag()
				    .on('start', dragStarted)
				    .on('drag', dragged.bind(this))
				    .on('end', dragEnded.bind(this))
			    );
			    
			const valueRect = sliderGroup.append('rect')
			    .attr('class', 'value-rect')
			    .attr('fill', 'rgba(255, 255, 255, 0.5)')
		        .attr('y', height - 14 - circleRadius)
			    .attr('rx', 5)
			    .attr('ry', 5);

		    const valueDisplay = sliderGroup.append('text')
		        .attr('class', 'value-display')
		        .attr('x', width / 2)
		        .attr('y', height - circleRadius * 2)
		        .attr('text-anchor', 'middle')
		        .attr('dominant-baseline', 'hanging')
		        .style('font-family', 'Arial')
		        .style('font-size', '12px')
		        .style('fill', '#000');
		
			this.scaleWidth = width; // Used if resized
		    this.valueDisplay = valueDisplay;	
		    this.valueRect = valueRect;			
			this.updateValueDisplay(sliderGroup, binBounds, binInterval, width);

			let initialRectX;
			let initialCursorRectX;
			let initialBarWidth;
			
			function dragStarted(d, i, nodes) {
			    d3.select(nodes[i]).style("stroke", "red");
			    if (nodes[i].tagName.toLowerCase() === 'rect') {
					initialRectX = parseFloat(d3.select(nodes[i]).attr('x'));
					initialCursorRectX = d3.event.x;
					initialBarWidth = parseFloat(d3.select(nodes[i]).attr('width'));
				}
				else {
			        d3.select(nodes[i]).raise();
			    }
			}
			
			function dragEnded(d, i, nodes) {
			    d3.select(nodes[i]).style("stroke", null); // Reset stroke style
			}
			
			function dragged(d, i, nodes) {
			    const newX = Math.max(0, Math.min(width, d3.event.x));
			    
			    this.fromX = parseFloat(d3.select(nodes[0]).attr('cx'));
			    this.toX = parseFloat(d3.select(nodes[1]).attr('cx'));
			    
			    if (i === 0 && newX <= this.toX) {
			    	d3.select(nodes[i]).attr('cx', newX);
			    	this.fromX = newX;
				}
				else if (i === 1 && newX >= this.fromX) {
			    	d3.select(nodes[i]).attr('cx', newX);
			    	this.toX = newX;					
				}
				
			    // Update range rectangle position and size	
			    sliderGroup.select('rect')
			        .attr('x', this.fromX)
			        .attr('width', this.toX - this.fromX);
			    
                this.updateValueDisplay(sliderGroup, binBounds, binInterval, width);    
			    this.onChangeCallback(this.fromValue, this.toValue, this.includeUndated);
			        
			}
			
			function draggedBar(d, i, nodes) {
			    const newCursorRectX = Math.max(0, Math.min(width, d3.event.x));
			    const newRectX = Math.max(0, Math.min(width - initialBarWidth, newCursorRectX + initialRectX - initialCursorRectX));
			    
			    sliderGroup.selectAll('rect').attr('x', newRectX);
			    sliderGroup.selectAll('.left-handle').attr('cx', newRectX);
				sliderGroup.selectAll('.right-handle').attr('cx', newRectX + initialBarWidth);

                this.updateValueDisplay(sliderGroup, binBounds, binInterval, width);   
			    this.onChangeCallback(this.fromValue, this.toValue, this.includeUndated);
			}

			sliderGroup.on('mouseover', () => {
			    this.valueDisplay.attr('display', 'block');
			    this.valueRect.attr('display', 'block');
			}).on('mouseout', () => {
			    this.valueDisplay.attr('display', 'none');
			    this.valueRect.attr('display', 'none');
			});			
			
		}
 
	}
    
	updateValueDisplay(sliderGroup, binBounds, binInterval, width) {
	    // Get the x positions of the left and right handles (circles)
	    const leftHandleX = parseFloat(sliderGroup.select('.left-handle').attr('cx'));
	    const rightHandleX = parseFloat(sliderGroup.select('.right-handle').attr('cx'));
	    
	    // Calculate the corresponding values based on the positions
	    this.fromValue = binBounds[Math.floor(leftHandleX / (width / binBounds.length))];
	    this.toValue = binInterval + (binBounds[Math.floor(rightHandleX / (width / binBounds.length))] || binBounds[binBounds.length - 1]);
	
	    // Update the value display
    	const centerX = (leftHandleX + rightHandleX) / 2;
	    const text = `${this.fromValue} - ${this.toValue}`;
	
	    const textWidth = this.calculateTextWidth(text);
	    const rectWidth = textWidth + 10;
	    const rectHeight = 20;
	    const rectX = centerX - rectWidth / 2;
	    
	    const rect = sliderGroup.select('.value-rect');
	    rect.attr('x', rectX)
	        .attr('width', rectWidth)
	        .attr('height', rectHeight);

	    this.valueDisplay
	    	.text(`${this.fromValue} - ${this.toValue}`)
        	.attr('x', centerX);
	}
	    
	calculateTextWidth(text) {
	    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	    svg.style.position = 'absolute';
	    svg.style.visibility = 'hidden';
	    document.body.appendChild(svg);
	
	    const textElement = document.createElementNS("http://www.w3.org/2000/svg", "text");
	    textElement.textContent = text;
	    svg.appendChild(textElement);
	    const width = textElement.getBBox().width;
	
	    document.body.removeChild(svg);
	    return width;
	}   

    appendUndatedCheckbox() {
        if (this.includeUndated !== null) {
            const buttonHTML = `
                <div class="undated_container" title="Include features without temporal data.">
                    <input type="checkbox" id="undated_checkbox"${this.includeUndated ? ' checked' : ''} />
                    <label for="undated_checkbox">Undated</label>
                </div>
            `;
            this.container.insertAdjacentHTML('beforeend', buttonHTML);
            const checkbox = document.getElementById('undated_checkbox');
            checkbox.addEventListener('change', () => {
                this.includeUndated = checkbox.checked;
			    this.onChangeCallback(this.fromValue, this.toValue, this.includeUndated);
            });
        }
    }
    
    destroy() {
        window.removeEventListener('resize', this.initialise);
    }
    
    appendStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .range-slider {
                cursor: ew-resize;
            }
			#historygram {
			    user-select: none;
			    -webkit-user-select: none; /* For Safari */
			    -moz-user-select: none; /* For Firefox */
			    -ms-user-select: none; /* For Internet Explorer/Edge */
			}            
        `;
        document.head.appendChild(style);
    }

}
