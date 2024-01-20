const paintStyles = { // Customisation of this object will be reflected in the style of all layers with the 'places' source.
	'Polygon': {
		'fill-color': [
			'rgba(0,128,0,.4)', // green
			'rgba(221,221,221,.3)' // pale-gray
		],
		'fill-outline-color': [
			'red', 
			['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], 'rgba(102,102,102,.5)', // dark-gray
			'rgba(102,102,102,.8)' // dark-gray
		],
	},
	'LineString': {
		'line-color': [
			'rgba(0,128,0,.4)', // green
			'rgba(144,238,144,.8)' // lightgreen
		],
		'line-width': [
			2,
			1
		]
	},
	'Point': {
        'circle-color': [
			'rgba(255,0,0)', // red
			['all', ['has', 'green'], ['==', ['get', 'green'], true]], 'rgba(0, 128, 0)', // green
			'rgba(255,165,0)' // orange
        ],
        'circle-opacity': [
			0.2,
			.7
        ],
		'circle-radius': [
			[
				'interpolate',
				['linear'],
				['zoom'],
				0, .5, // zoom, radius
				16, 20,
			],
			[
			'interpolate',
				['linear'],
				['zoom'],
				0, .3, // zoom, radius
				16, 12,
			]
		],
		'circle-stroke-color': [
			'rgb(255,0,0)',	// red
			['all', ['has', 'green'], ['==', ['get', 'green'], true]], 'rgba(0, 128, 0)', // green		
			'rgb(255,165,0)' // orange
        ],
		'circle-stroke-opacity': [
			.9,
			['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], .3,
			.7
        ],
		'circle-stroke-width': [
			7,
			3
		],
	}
}

class Layerset {
    constructor(mapInstance, dc_id, source='places') {
		this._map = mapInstance;
		this._highlighter = ['match', ['get', 'pid'], []];
		this._layerIDs = [];
		this._source = source;
		
		Object.keys(paintStyles).forEach((geometryType) => {
			const paintStyle = paintStyles[geometryType];
			const layerID = `${dc_id}_${geometryType.toLowerCase()}`;
			
			Object.keys(paintStyle).forEach((attribute) => {
				paintStyle[attribute] = [...this._highlighter, ...paintStyle[attribute]];
			});
			
			const layer = {
			    'id': layerID,
			    'type': Object.keys(paintStyle)[0].split('-')[0], // fill|line|circle
			    'source': source,
			    'paint': paintStyle,
			    'filter': ['==', '$type', geometryType],
			};
			mapInstance.addLayer(layer);
			this._layerIDs.push(layerID);
			
		});		
		
    }

    onAdd() {
    }

    onRemove() {
		this._layerIDs.forEach((layerID) => {
			mapInstance.removeLayer(layerID);
		});
    }
    
    _applyHighlighter(highlighter) {
		this._layerIDs.forEach((layerID) => {
			Object.keys(paintStyles).forEach((geometryType) => {
				const paintStyle = paintStyles[geometryType];
				Object.keys(paintStyle).forEach((attribute) => {
					this._map.setPaintProperty(layerID, attribute, [...highlighter, ...paintStyle[attribute]]);
				});
			});
		});		
	}
    
    highlight(pids) { // pids is an array of pids whose features should be highlighted
    	var highlighter = this._highlighter;
    	highlighter[2] = pids;
    	this._applyHighlighter(highlighter);
	}
	
	reset() {
    	this._applyHighlighter(this._highlighter);
	}
}

export default Layerset;