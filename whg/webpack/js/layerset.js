// layerset.js

class Layerset {
    constructor(mapInstance, dc_id, source_id, paintOption, colour, colour_highlight, number, enlarger, relation_colors) {
		// The following default colours must be expressed in rgba format
		this.colour = (typeof colour !== 'string') ? 'rgba(255,165,0,1)' : colour; // orange
		this.colour_outline = 'rgba(0,0,0,1)'; // black
		this.colour_water = 'rgba(0,0,255,1)'; // blue
		this.colour_highlight = (typeof colour_highlight !== 'string') ? 'rgba(255,0,0,1)' : colour_highlight; // red
		
		this.number = (number === undefined) ? false : number;
		this.enlarger = (enlarger === undefined) ? 1 : enlarger;
		
		this.colour_options = [
		    this.colour_highlight,
			['all', !relation_colors, ['has', 'fclasses'], ['in', 'H', ['get', 'fclasses']]], this.colour_water, // blue
			relation_colors 
			? ['match', ['get', 'relation'], ...relation_colors, this.colour]
			: this.colour
		]

		const paintOptions = {
			'standard': {
				// A `feature-state`-based `highlighter` condition is applied dynamically to each of the expressions given below
				'Polygon': {
					'fill-color': this.colour_options,
			        'fill-opacity': [
						0.5,
						.2
			        ],
					'fill-antialias': false, // Disables what would be a virtually-invisible 1px outline
				},
				'Polygon-line': { // Add extra layer to enable polygon outline styling
					'line-color': [
					    this.colour_highlight,
					    this.colour_outline
					],
					'line-width': [
			            'interpolate', ['exponential', 2], ['zoom'],
			            0, 1, // zoom level, line width
			            10, 5, // zoom level, line width
			        ],
			        'line-opacity': [
						0.5,
						.7
			        ],
			        'line-dasharray': ["literal", [4, 2]]
				},
				'LineString': {
					'line-color': this.colour_options,
					'line-width': [
			            'interpolate', ['exponential', 2], ['zoom'],
			            0, 4, // zoom level, line width
			            10, 10, // zoom level, line width
			        ],
			        'line-opacity': [
						0.5,
						.4
			        ]
				},
				'Point': {
			        'circle-color': this.colour_options,
			        'circle-opacity': [
						0.2,
						.85
			        ],
					'circle-radius': [
			            'interpolate', ['exponential', 2], ['zoom'],
			            0, Math.max(3, .5 * this.enlarger), // zoom level, radius
			            10, Math.max(13, .5 * this.enlarger), // zoom level, radius
			            18, 20 // zoom level, radius
					],
					'circle-stroke-color': [
					    this.colour_highlight,
					    this.colour_outline
					],
					'circle-stroke-opacity': [
						.9,
						['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], .3,
						.7
			        ],
					'circle-stroke-width': [
						7,
						1
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
					'fill-color': 'rgba(255,0,0,.1)', // red
					'fill-outline-color': 'rgba(255,0,0,.7)' // red
				}
			},
			'userareas': {
				'Polygon': {
					'fill-color': 'rgba(255,0,0,.1)', // red
					'fill-outline-color': 'rgba(255,0,0,.7)' // red
				}
			},
			'hulls': {
				'Polygon': {
					'fill-color': 'rgba(255,0,0,.1)', // red
					'fill-outline-color': 'rgba(0,128,0,.8)', // green
				}
			}
		}	
		
		this._style = JSON.parse(JSON.stringify(paintOptions[paintOption || 'standard'])); // Clone `standard` by default
		
		this._map = mapInstance;
		this._highlighter = ['case', ['boolean', ['feature-state', 'highlight'], false]]
		this._layerIDs = [];
		this._source = source_id || dc_id; // Use `dc_id` if `source_id` is not given
		var source = this._map.getSource(this._source);
		this._sourceLayer = (!!source.type && source.type == 'vector') ? 'features' : '';
		
		console.log('source',this._map.getSource(this._source));
		
		Object.keys(this._style).forEach((geometryType) => {
			let paintGeometryStyle = this._style[geometryType];
			const layerID = `${this._source}_${geometryType.toLowerCase()}`;
			
			Object.keys(paintGeometryStyle).forEach((attribute) => {
				if ((!paintOption || paintOption == 'standard') && !['circle-radius','fill-antialias','line-width','line-dasharray'].includes(attribute)) {
					paintGeometryStyle[attribute] = [...this._highlighter, ...paintGeometryStyle[attribute]];
				}
			});
			
			const layer = {
			    'id': layerID,
			    'type': Object.keys(paintGeometryStyle)[0].split('-')[0], // fill|line|circle
			    'source': this._source,
			    'source-layer': this._sourceLayer,
			    'paint': paintGeometryStyle,
			    'filter': ['==', '$type', geometryType.split('-')[0]],
			};
			console.log(layer);
			mapInstance.addLayer(layer);
			this._layerIDs.push(layerID);
			
		});

		if (this.number) {
			const layerID = `${this._source}_numbers`;
			mapInstance.addLayer({
	            'id': layerID,
	            'type': 'symbol',
	            'source': this._source,
	            'layout': {
	                'text-field': ['to-string', ['id']], // Uses index `id` property from feature root, not `properties.id`  
	                'text-size': 12,
	                'text-offset': [0, 0],
	                'text-anchor': 'center',
	            },
	            'paint': {
					'text-color': 'white',
				},
	        });
	        this._layerIDs.push(layerID);
		}
		
		return this;
		
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

    toggleVisibility(show) {
        // If `show` parameter is provided, use it to set visibility, otherwise toggle present state
        const visibility = typeof show === 'boolean' ? (show ? 'visible' : 'none') : null;
        this._layerIDs.forEach((layerID) => {
            const layer = this._map.getLayer(layerID);
            if (layer) {
                const currentVisibility = this._map.getLayoutProperty(layerID, 'visibility');
                const newVisibility = visibility !== null ? visibility : (currentVisibility === 'visible' ? 'none' : 'visible');
                this._map.setLayoutProperty(layerID, 'visibility', newVisibility);
            }
        });
    }
}

export default Layerset;