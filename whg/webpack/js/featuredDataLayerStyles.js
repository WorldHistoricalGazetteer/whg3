const featuredDataLayers = { // IMPORTANT: Listed in order of addition to the map
	default: [
		{
	        id: 'polygons',
	        type: 'fill',
	        source: 'featured-data-source',
	        paint: {
		        'fill-outline-color': 'red',
	            'fill-color': 'pink',
	            'fill-opacity': 0.7,
	        },
	        'filter': ['==', '$type', 'Polygon']
	    },
	    {
		    id: 'lines',
		    type: 'line',
		    source: 'featured-data-source',
		    paint: {
		        'line-color': 'red',
		        'line-opacity': 0.7,
		        'line-width': 2,
		    },
		    filter: ['==', '$type', 'LineString'],
		},
		{
				id: 'points',
		    type: 'circle',
		    source: 'featured-data-source',
		    paint: {
		        'circle-radius': 6,
		        'circle-color': 'pink',
		        'circle-opacity': 0.7,
		        'circle-stroke-color': 'red',
		        'circle-stroke-width': 2,
		    },
	        'filter': ['==', '$type', 'Point'],
		}
	],
	heatmap: [
	    {
	        id: 'heatmap-heat',
	        type: 'heatmap',
	        source: 'featured-data-source',
	        maxzoom: 14,
	        paint: {
	
	          // Increase the heatmap weight based on area magnitude
	          'heatmap-weight': [
	            'interpolate',
	            ['linear'],
	            ['get', 'area'],
	            0,
	            0,
	            1,
	            1
	          ],
	
	          // Increase the heatmap color weight weight by zoom level
	          // heatmap-intensity is a multiplier on top of heatmap-weight
	          'heatmap-intensity': [
	            'interpolate',
	            ['linear'],
	            ['zoom'],
	            0,
	            1,
	            12,
	            3
	          ],
	
	          // Color ramp for heatmap.  Domain is 0 (low) to 1 (high).
	          // Begin color ramp at 0-stop with a 0-transparancy color
	          // to create a blur-like effect.
	          'heatmap-color': [
	            'interpolate',
	            ['linear'],
	            ['heatmap-density'],
	            0, "rgba(68, 1, 84, 0)",
	            0.01, "rgba(68, 1, 84, 0.2)",
	            0.13, "rgba(71, 44, 122, 1)",
	            0.25, "rgba(59, 81, 139, 1)",
	            0.38, "rgba(44, 113, 142, 1)",
	            0.5, "rgba(33, 144, 141, 1)",
	            0.63, "rgba(39, 173, 129, 1)",
	            0.75, "rgba(92, 200, 99, 1)",
	            0.88, "rgba(170, 220, 50, 1)",
	            1, "rgba(253, 231, 37, 1)",
	          ],
	
	          // Adjust the heatmap radius by zoom level
	          'heatmap-radius': [
	            'interpolate',
	            ['linear'],
	            ['zoom'],
	            0,
	            2,
	            9,
	            20
	          ],
	          // Transition from heatmap to circle layer by zoom level
	          'heatmap-opacity': [
	            'interpolate',
	            ['linear'],
	            ['zoom'],
	            7,
	            1,
	            18,
	            0
	          ]
	        }
	      },
	      {
	        'id': 'heatmap-point',
	        'type': 'circle',
	        'source': 'featured-data-source',
	        'minzoom': 8,
	        'paint': {
	          'circle-pitch-alignment': "map",
	          // Size circle radius by area magnitude and zoom level
	          'circle-radius': [
	            'interpolate',
	            ['linear'],
	            ['zoom'],
	            9,
	            ['interpolate', ['linear'], ['get', 'area'], 0, 0.1 * 5, 1, 2 * 2.5],
	            16,
	            ['interpolate', ['linear'], ['get', 'area'], 0, 1 * 5, 1, 20 * 2.5]
	          ],
	          // Color circle by area magnitude
	          'circle-color': [
	            'interpolate',
	            ['linear'],
	            ['get', 'area'],
	            0, "rgba(68, 1, 84, 0)",
	            0.01, "rgba(68, 1, 84, 20)",
	            0.13, "rgba(71, 44, 122, 100)",
	            0.25, "rgba(59, 81, 139, 100)",
	            0.38, "rgba(44, 113, 142, 100)",
	            0.5, "rgba(33, 144, 141, 100)",
	            0.63, "rgba(39, 173, 129, 100)",
	            0.75, "rgba(92, 200, 99, 100)",
	            0.88, "rgba(170, 220, 50, 100)",
	            1, "rgba(253, 231, 37, 100)",
	          ],
	          // 'circle-stroke-color': 'white',
	          'circle-stroke-width': 0,
	          // Transition from heatmap to circle layer by zoom level
	          'circle-opacity': [
	            'interpolate',
	            ['linear'],
	            ['zoom'],
	            8,
	            0,
	            12,
	            0.8
	          ]
	        }
	      }
	 ]
}

export default featuredDataLayers;
