/*
  Author: Stephen Gadd, Docuracy Ltd
  File: dateline.js
  Description: JavaScript date range selector

  Copyright (c) 2023 Stephen Gadd
  Licensed under the Creative Commons Attribution 4.0 International License (CC-BY 4.0).
*/

function fillSlider(from, to) {
	const rangeDistance = to.max - to.min;
	const fromPosition = from.value - to.min;
	const toPosition = to.value - to.min;
	to.style.zIndex = `3`;
	to.style.background = `linear-gradient(
    to right,
    ${"var(--slider-background)"} 0%,
    ${"var(--slider-background)"} ${(fromPosition / rangeDistance) * 100}%,
    ${"var(--range-color)"} ${(fromPosition / rangeDistance) * 100}%,
    ${"var(--range-color)"} ${(toPosition / rangeDistance) * 100}%,
    ${"var(--slider-background)"} ${(toPosition / rangeDistance) * 100}%,
    ${"var(--slider-background)"} 100%)`;
}

function formatTooltipContent(fromValue, toValue) {
	if (fromValue === toValue) {
		return `${fromValue}`;
	} else {
		return `${fromValue}-${toValue}`;
	}
}

function calculateLabelWidth(container, value) {
	// Create a dummy label element to calculate its width
	const dummyLabel = document.createElement('div');
	dummyLabel.classList.add('value-label');
	dummyLabel.textContent = value;
	container.appendChild(dummyLabel);
	const labelWidth = dummyLabel.offsetWidth;
	container.removeChild(dummyLabel); // Remove the dummy label after measurement
	return {
		element: dummyLabel,
		width: labelWidth
	};
}

class Dateline {
	constructor({
		fromValue = 1300,
		toValue = 1964,
		minValue = 1066,
		maxValue = 2000,
		onChange = null,
		open = false,
		epochs = true,
		automate = true
	}) {
		this.fromValue = fromValue;
		this.toValue = toValue;
		this.minValue = minValue;
		this.maxValue = maxValue;
		this.open = open;
		this.epochs = epochs;
		this.automate = automate;

		this.createSliderElements();
		this.updateFormInputs();

		this.addGoogleFont();

		this.observeResize();
		
		this.onChangeCallback = onChange;
	}

	addGoogleFont() {
		const fontLink = document.createElement("link");
		fontLink.href = "https://fonts.googleapis.com/css2?family=REM&display=swap";
		fontLink.rel = "stylesheet";
		document.head.appendChild(fontLink);

		// Add the CSS rules for the range_container
		const style = document.createElement("style");
		style.innerHTML = `
	      .range_container {
	        font-family: 'REM', sans-serif;
	      }
	    `;
		document.head.appendChild(style);
	}

	createSliderElements() {
		const rangeContainerHTML = `
			<div class="range_container">
				<div class="form_control">
					<div class="control_container from">
						<button class="year_button">${this.fromValue}</button>
						${this.epochs ? '<button class="epochs_button" title="Set range from a defined epoch.">Epochs</button>' : ''}
						${this.automate ? '<button class="automate_button" title="Automate slider movement.">Automate</button>' : ''}
					</div>
					<div class="control_container to">
						<button class="year_button">${this.toValue}</button>
					</div>
				</div>
				<input type="range" value="${this.fromValue}" min="${this.minValue}" max="${this.maxValue}" class="slider from" id="fromSlider">
				<input type="range" value="${this.toValue}" min="${this.minValue}" max="${this.maxValue}" class="slider to" id="toSlider">
				<div class="tooltip">${formatTooltipContent(this.fromValue, this.toValue)}</div>
				<div class="scale-container"></div>
				<button class="dateline-button expanded" title="Toggle date filtering"><span></span></button>
			</div>
		`;
		const parser = new DOMParser();
		this.rangeContainer = parser.parseFromString(rangeContainerHTML, 'text/html').body.firstChild;
		document.getElementById("dateline").appendChild(this.rangeContainer);

		const datelineButton = document.querySelector('.dateline-button');
		this.rangeContainer.parentNode.insertBefore(datelineButton, this.rangeContainer);
		datelineButton.addEventListener('click', () => {
			if (this.rangeContainer.classList.contains('transitioned')) {
				this.rangeContainer.classList.remove('transitioned');
			}
			this.rangeContainer.classList.toggle('expanded');
			const onTransitionEnd = (event) => {
				if ((event.propertyName === 'max-width') && this.rangeContainer.classList.contains('expanded')) {
					if (!this.scaleContainer.hasChildNodes()) {
						this.addSliderScale(this.scaleContainer);
					}
					this.rangeContainer.removeEventListener('transitionend', onTransitionEnd);
					this.rangeContainer.classList.add('transitioned');
				}
			};

			this.rangeContainer.addEventListener('transitionend', onTransitionEnd);
		});

		this.fromSlider = this.rangeContainer.querySelector('.slider.from');
		this.toSlider = this.rangeContainer.querySelector('.slider.to');
		this.tooltip = this.rangeContainer.querySelector('.tooltip');
		this.scaleContainer = this.rangeContainer.querySelector('.scale-container');
		fillSlider(this.fromSlider, this.toSlider);

		const updateTooltip = (event) => {
			const slider = this.fromSlider;
			const rect = slider.getBoundingClientRect();
			const sliderWidth = slider.offsetWidth;
			let offsetX;

			if (event.clientX !== undefined) {
				offsetX = event.clientX - rect.left;
			} else if (event.changedTouches && event.changedTouches[0].clientX !== undefined) {
				offsetX = event.changedTouches[0].clientX - rect.left;
			} else {
				return; // Return early if neither mouse nor touch event
			}
			this.tooltip.textContent = formatTooltipContent(this.fromSlider.value, this.toSlider.value);

			// Calculate the left offset of the tooltip to center it on the mouse
			const tooltipWidth = this.tooltip.offsetWidth;
			const tooltipLeft = offsetX - tooltipWidth / 2;

			// Prevent the tooltip from going beyond the slider boundaries
			const minLeft = 0;
			const maxLeft = sliderWidth - tooltipWidth;
			this.tooltip.style.left = `${Math.min(maxLeft, Math.max(minLeft, tooltipLeft))}px`;
		};

		this.rangeContainer.addEventListener("mouseleave", () => {
			this.tooltip.style.opacity = 0; // Hide the tooltip when mouse leaves the rangeContainer
		});

		[this.fromSlider, this.toSlider].forEach(slider => {
			slider.addEventListener("mouseenter", () => {
				this.tooltip.style.opacity = 1;
			});
			slider.addEventListener("mouseleave", () => {
				this.tooltip.style.opacity = 0;
			});
			slider.addEventListener("mousemove", (event) => {
				updateTooltip(event);
			});
			slider.addEventListener('input', event => {
				if (event.target.classList.contains('to')) {
					this.toValue = parseInt(event.target.value);
					if (this.toValue <= this.fromValue) {
						this.fromValue = this.toValue;
						this.fromSlider.value = this.fromValue;
					}
				} else { // from
					this.fromValue = parseInt(event.target.value);
					if (this.fromValue >= this.toValue) {
						this.toValue = this.fromValue;
						this.toSlider.value = this.toValue;
					}
				}
				this.updateFormInputs();
			});
		});

		if (this.open) {
			const datelineButton = document.querySelector('.dateline-button');
			datelineButton.click();
			this.rangeContainer.classList.add('transitioned');
		}
	}

	observeResize() {
		this.resizeObserver = new ResizeObserver(entries => {
			for (const entry of entries) {
				if (entry.target === document.getElementById("dateline") && this.rangeContainer.classList.contains('expanded')) {
					this.addSliderScale(this.scaleContainer);
				}
			}
		});
		this.resizeObserver.observe(document.getElementById("dateline"));
	}

	addSliderScale(scaleContainer) {

		function calculateFirstAndLastLabels(minValue, maxValue, scale, divisions, maxLabels) {
			for (const division of divisions) {
				const powerOfTen = Math.pow(10, scale - 1);
				const divisor = powerOfTen * division;
				const firstLabel = Math.ceil(minValue / divisor) * divisor;
				const lastLabel = Math.floor(maxValue / divisor) * divisor;
				const labelCount = 1 + (lastLabel - firstLabel) / divisor;
				if (labelCount < maxLabels) {
					let firstTick = firstLabel;
					const tickStep = divisor / division;
					while (firstTick >= minValue) {
						firstTick -= tickStep;
					}
					firstTick += tickStep;
					// console.log(firstLabel, lastLabel, labelCount, divisor, division, firstTick, tickStep);
					return {
						firstLabel,
						lastLabel,
						labelCount,
						divisor,
						division,
						firstTick,
						tickStep
					};
				}
			}
			console.log('No label scaling determined.');
			return {};
		}

		const maxLabels = Math.floor(scaleContainer.offsetWidth / (1.6 * calculateLabelWidth(scaleContainer, this.maxValue).width));
		const valueRange = this.maxValue - this.minValue;
		const divisions = [1, 2, 5, 10, 20, 50];
		const minStep = Math.floor(valueRange / maxLabels);
		const scale = minStep.toString().length;

		const {
			firstLabel,
			lastLabel,
			labelCount,
			divisor,
			division,
			firstTick,
			tickStep
		} = calculateFirstAndLastLabels(this.minValue, this.maxValue, scale, divisions, maxLabels);

		scaleContainer.innerHTML = ''; // Clear the scale container in case of re-sizing
		let tickValue = firstTick;
		while (tickValue <= this.maxValue) {
			const tick = document.createElement('div');
			tick.classList.add('tick');
			tick.style.left = `${((tickValue - this.minValue) / valueRange) * 100}%`;

			if (tickValue % divisor === 0) {
				tick.classList.add("labeled-tick"); // Add the class for labeled ticks
				const {
					element: valueLabel,
					width: labelWidth
				} = calculateLabelWidth(scaleContainer, tickValue);
				valueLabel.textContent = tickValue;
				scaleContainer.appendChild(valueLabel);

				// Calculate the position for the label to center it on the tick
				const labelLeft = ((tickValue - this.minValue) / valueRange) * 100;

				// Adjust labelLeft to ensure the label is not off the slider boundaries
				const minLeft = (labelWidth / scaleContainer.offsetWidth) * 100 / 2;
				const maxLeft = 100 - minLeft;
				valueLabel.style.left = `${Math.min(maxLeft, Math.max(minLeft, labelLeft))}%`;
			}
			scaleContainer.appendChild(tick);

			tickValue += tickStep;
		}
	}

	updateFormInputs() {
		this.rangeContainer.querySelector('.control_container.from .year_button').textContent = this.fromValue;
		this.rangeContainer.querySelector('.control_container.to .year_button').textContent = this.toValue;
		fillSlider(this.fromSlider, this.toSlider);
		
		if (typeof this.onChangeCallback === 'function') {
            this.onChangeCallback(this.fromValue, this.toValue);
        }
	}
}