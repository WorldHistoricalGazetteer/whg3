const datasetLayers = [ // IMPORTANT: Listed in order of addition to the map
	{
		'id': 'gl_active_poly',
		'type': 'fill',
		'source': 'places',
		'paint': {
			'fill-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0,.4)', // green
				'rgba(221,221,221,.3)' // pale-gray
			],
			'fill-outline-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'red',
				['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], 'rgba(102,102,102,.5)', // dark-gray
				'rgba(102,102,102,.8)' // dark-gray
			],
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'gl_active_line',
		'type': 'line',
		'source': 'places',
		'paint': {
			'line-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0,.4)', // green
				'rgba(144,238,144,.8)' // lightgreen
			],
			'line-width': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 2,
				1
			]
		},
		'filter': ['==', '$type', 'LineString']
	},
	{
		'id': 'outline',
		'type': 'line',
		'source': 'places',
		'layout': {},
		'paint': {
			'line-color': 'rgba(153,153,153,.5)', // mid-gray
			'line-width': 1,
			'line-dasharray': [4, 2],
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'gl_active_point',
		'type': 'circle',
		'source': 'places',
		'paint': {
	        'circle-color': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(255,0,0)', // red
				['has', 'reconciliation'], 'rgba(0, 128, 0)', // green
				'rgba(255,165,0)' // orange
	        ],
	        'circle-opacity': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 0.2,
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
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgb(255,0,0)',	// red
				['has', 'reconciliation'], 'rgba(0, 128, 0)', // green		
				'rgb(255,165,0)' // orange
	        ],
			'circle-stroke-opacity': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], .9,
				['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], .3,
				.7
	        ],
			'circle-stroke-width': [ // Simulate larger radius - zoom-based radius cannot operate together with feature-state switching
				'case',
				['boolean', ['feature-state', 'highlight'], false], 7,
				3
			],
		},
		'filter': ['==', '$type', 'Point'],
	}
]

export default datasetLayers;
