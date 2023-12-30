// mapSequenceArcs.js

import { representativePoint } from './utilities';

export default class SequenceArcs {
	constructor(map, dataset, {
        facet = 'seq', // Property to use for sorting
        order = 'asc', // 'asc'|'desc' - Sort order
		animationRate = 1, // animationRate = steps per second
		deflectionValue = 1,
		lineColor = '#888',
		lineOpacity = .8,
		lineWidth = 1,
		dashLength = 8
	} = {}) {
		this.map = map;
		this.dataset = this.convertToRepresentativePoints(dataset);
		this.arcSourceId = 'sequence-arcs-source';
		this.arcLayerId = 'sequence-arcs-layer';
		if(!this.map.getSource(this.arcSourceId)) {
			window.additionalLayers.push([this.arcSourceId, this.arcLayerId]);
		}
		else {
			this.map.removeLayer(this.arcLayerId);
			this.map.removeSource(this.arcSourceId);
		}
		this.facet = facet;
		this.sortOrder = (order === 'desc') ? -1 : 1;		
        this.deflectionValue = deflectionValue; // Defines curvature of arc (displacement of arc's centre-point is proportional to its length)
		this.lineColor = lineColor;
		this.lineOpacity = lineOpacity;
		this.lineWidth = lineWidth;
		this.dashLength = dashLength; // Must be > 0
		this.animationInterval = animationRate > 0 ? 1000 / (animationRate * dashLength * 1.5) : null; // animationRate is number of full dash-cycles per second
		this.dashArraySequence = animationRate > 0 ? this.generateDashArraySequence() : [
			[1, 0]
		]; // Draw solid line if no animation
		this.createArcs();
		this.createArcLayer();
		if (animationRate > 0) this.animateDashedLine();
	}

	createArcs() {
		const arcFeatures = [];

		function calculateControlPoint(start, end, baseDeflection) {
			const lineLength = distance(start, end, {
				units: 'kilometers'
			});
			const deflection = baseDeflection * lineLength / 1000;

			const midX = (start[0] + end[0]) / 2;
			const midY = (start[1] + end[1]) / 2;
			const angle = Math.atan2(end[1] - start[1], end[0] - start[0]) + Math.PI / 2;
			const controlX = midX + deflection * Math.cos(angle);
			const controlY = midY + deflection * Math.sin(angle);
			return [controlX, controlY];
		}

		if (this.dataset && this.dataset.type === 'FeatureCollection') {
			const sortedData = this.dataset.features.sort((a, b) => {
				return this.sortOrder * (a.properties[this.facet] - b.properties[this.facet]);
            });

			for (let i = 0; i < sortedData.length - 1; i++) {
				const startPoint = sortedData[i];
				const endPoint = sortedData[i + 1];

				const controlPoint = calculateControlPoint(
					startPoint.geometry.coordinates,
					endPoint.geometry.coordinates,
					this.deflectionValue
				);

				const line = lineString([
					startPoint.geometry.coordinates,
					controlPoint,
					endPoint.geometry.coordinates,
				]);

				const arc = bezierSpline(line, {
					sharpness: 1
				});

				arcFeatures.push(arc);
			}

			this.arcFeatures = arcFeatures;

			this.map.addSource(this.arcSourceId, {
				type: 'geojson',
				data: {
					type: 'FeatureCollection',
					features: this.arcFeatures
				},
			})

		}
	}

	createArcLayer() {
	    const layers = this.map.getStyle().layers;
        // Find the index of the highest layer whose id begins with 'gl_active_point'
        let topPointLayer;
        for (let i = layers.length - 1; i < layers.length; i--) {
            if (layers[i].id.startsWith('gl_active_point')) {
                topPointLayer = layers[i].id;
                break;
            }
        }
	
	    this.map.addLayer({
	        id: this.arcLayerId,
	        type: 'line',
	        source: this.arcSourceId,
	        paint: {
	            'line-color': this.lineColor,
	            'line-opacity': this.lineOpacity,
	            'line-width': this.lineWidth,
	            'line-dasharray': this.dashArraySequence[0],
	        },
	    }, topPointLayer);
	}

	generateDashArraySequence() {
		const dashArraySequence = [];
		const dashLength = this.dashLength; // Maximum dash value in the sequence
		const gapLength = dashLength / 2; // Gap value between dashes

		for (let i = 0; i <= dashLength; i++) {
			dashArraySequence.push([i, gapLength, dashLength - i]);
		}

		for (let i = 0; i <= gapLength; i++) {
			dashArraySequence.push([0, i, dashLength, gapLength - i]);
		}

		return dashArraySequence;
	}

	animateDashedLine() {
		let step = 0;
		let lastTimestamp = 0;
		const animateDashArray = (timestamp) => {
			const elapsedTime = timestamp - lastTimestamp;
			if (elapsedTime >= this.animationInterval) {
				lastTimestamp = timestamp;
				const newStep = (step + 1) % this.dashArraySequence.length;
				this.map.setPaintProperty(
					this.arcLayerId,
					'line-dasharray',
					this.dashArraySequence[newStep]
				);
				step = newStep;
			}
			this.animationFrame = requestAnimationFrame(animateDashArray);
		}
		this.animationFrame = requestAnimationFrame(animateDashArray);
	}

	convertToRepresentativePoints(dataset) {
		if (dataset && dataset.type === 'FeatureCollection') {
			const convertedFeatures = dataset.features.map((feature) => {
				const representative = representativePoint(feature.geometry);
				return {
					type: 'Feature',
					properties: feature.properties,
					geometry: representative,
				};
			});
			return {
				type: 'FeatureCollection',
				features: convertedFeatures,
			};
		}
		console.log('Failed to convert dataset to representative points.');
		return dataset; // If the dataset is not a FeatureCollection, return it as is
	}
	
	destroy() {
        cancelAnimationFrame(this.animationFrame);
        window.additionalLayers = window.additionalLayers.filter(item =>
		  	JSON.stringify(item) !== JSON.stringify([this.arcSourceId, this.arcLayerId])
		);
        if (this.map.getLayer(this.arcLayerId)) {
            this.map.removeLayer(this.arcLayerId);
        }
        if (this.map.getSource(this.arcSourceId)) {
            this.map.removeSource(this.arcSourceId);
        }
        this.map = null;
        this.dataset = null;
        this.arcFeatures = null;
        return null;
    }
}