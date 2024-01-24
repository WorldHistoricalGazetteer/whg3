// layerset.js

const paintOptions = {
	'standard': {
		// A `feature-state`-based `highlighter` condition is applied dynamically to each of the expressions given below
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
				'interpolate',
				['linear'],
				['zoom'],
				0, .5, // zoom, radius
				16, 20,
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
	},
	'nearby-places': {
		'Polygon': {
			'fill-color': 'rgba(0,255,0,.3)', // green
			'fill-outline-color': 'rgba(0,255,0,.8)' // green
		},
		'LineString': {
			'line-color': 'rgba(0,255,0,.8)', // green
			'line-width': 1
		},
		'Point': {
	        'circle-color': 'rgb(0,255,0)', // green
	        'circle-opacity': .7,
			'circle-radius': [
				'interpolate',
				['linear'],
				['zoom'],
				0, .5, // zoom, radius
				16, 20,
			],
			'circle-stroke-color': 'rgb(0,255,0)', // green
			'circle-stroke-opacity': .7,
			'circle-stroke-width': 3,
		}
	},
	'countries': {
		'Polygon': {
			'fill-color': 'rgba(0,255,0,.3)', // green
			'fill-outline-color': 'rgba(0,255,0,.8)' // green
		}
	},
	'hulls': {
		'Polygon': {
			'fill-color': 'rgba(221,221,221,.3)', // pale-gray,
			'fill-outline-color': 'rgba(0,128,0,.8)', // green,
		}
	}
}

class Layerset {
    constructor(mapInstance, dc_id, source_id, paintOption) {
		this._map = mapInstance;
		this._highlighter = ['case', ['boolean', ['feature-state', 'highlight'], false]]
		this._layerIDs = [];
		this._source = source_id || dc_id; // Use `dc_id` if `source_id` is not given
		var source = this._map.getSource(this._source);
		this._sourceLayer = (!!source.type && source.type == 'vector') ? 'features' : '';
		this._style = JSON.parse(JSON.stringify(paintOptions[paintOption || 'standard'])); // Clone `standard` by default
		
		console.log('source',this._map.getSource(this._source));
		
		Object.keys(this._style).forEach((geometryType) => {
			let paintGeometryStyle = this._style[geometryType];
			const layerID = `${this._source}_${geometryType.toLowerCase()}`;
			
			Object.keys(paintGeometryStyle).forEach((attribute) => {
				if ((!paintOption || paintOption == 'standard') && attribute !== 'circle-radius') {
					paintGeometryStyle[attribute] = [...this._highlighter, ...paintGeometryStyle[attribute]];
				}
			});
			
			const layer = {
			    'id': layerID,
			    'type': Object.keys(paintGeometryStyle)[0].split('-')[0], // fill|line|circle
			    'source': this._source,
			    'source-layer': this._sourceLayer,
			    'paint': paintGeometryStyle,
			    'filter': ['==', '$type', geometryType],
			};
			console.log(layer);
			mapInstance.addLayer(layer);
			this._layerIDs.push(layerID);
			
		});
		
    }
    
    addFilter(filterOptions) {
		this._layerIDs.forEach((layerID) => {
			let filter = this._map.getFilter(layerID);
			filter = filter[0] == 'all' ? filter.push(filterOptions) : ['all', filter, filterOptions];
			this._map.setFilter(layerID, filter);
		});
	}

    onAdd() {
    }

    onRemove() {
		this._layerIDs.forEach((layerID) => {
			mapInstance.removeLayer(layerID);
		});
    }
}

export default Layerset;