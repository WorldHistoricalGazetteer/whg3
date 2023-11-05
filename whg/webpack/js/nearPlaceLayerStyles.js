const nearPlaceLayers = [ // IMPORTANT: Listed in order of addition to the map
	{
		'id': 'gl_active_poly_np',
		'type': 'fill',
		'source': 'nearbyPlaces',
		'paint': {
			'fill-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0,.4)', // green
				'rgba(0,255,0,.3)' // green
			],
			'fill-outline-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'red',
				['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], 'rgba(102,102,102,.5)', // dark-gray
				'rgba(0,255,0,.8)' // green
			],
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'gl_active_line_np',
		'type': 'line',
		'source': 'nearbyPlaces',
		'paint': {
			'line-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0,.4)', // green
				'rgba(0,255,0,.8)' // green
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
		'id': 'outline_np',
		'type': 'line',
		'source': 'nearbyPlaces',
		'layout': {},
		'paint': {
			'line-color': 'rgba(0,255,0,.5)', // green
			'line-width': 1,
			'line-dasharray': [4, 2],
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'gl_active_point_np',
		'type': 'circle',
		'source': 'nearbyPlaces',
		'paint': {
	        'circle-color': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(255,0,0)',	// red
				'rgb(0,255,0)' // green
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
				16, 10,
			],
			'circle-stroke-color': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgb(255,0,0)',	// red			
				'rgb(0,255,0)' // green
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

export default nearPlaceLayers;
