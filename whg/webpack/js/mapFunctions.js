// Control positioning of map, clear of overlays
export function getMapPadding(mappy, mapBounds) {
	const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
	const OverlaysRect = document.getElementById('mapOverlays').getBoundingClientRect();
	const mapPadding = {
		top: ControlsRect.top - OverlaysRect.top,
		bottom: OverlaysRect.bottom - ControlsRect.bottom,
		left: ControlsRect.left - OverlaysRect.left,
		right: OverlaysRect.right - ControlsRect.right,
	};
	if (mapBounds) {
		if (Array.isArray(mapBounds) || !mapBounds.hasOwnProperty('center')) { // mapBounds might be a coordinate pair object returned by mappy.getBounds();
			mappy.fitBounds(mapBounds, {
				padding: mapPadding,
				duration: 0
			});
		} else { // mapBounds has been set based on a center point and zoom
			mappy.flyTo({
				...mapBounds,
				padding: mapPadding,
				duration: 0
			})
		}
	}
	console.log('mapPadding calculated:', mapBounds, mapPadding);
	return mapPadding;
}

export function filteredLayer(layer, dateline) {
	if ($('.range_container.expanded').length > 0) { // Is dateline active?
		const modifiedLayer = ({
			...layer
		});
		const existingFilter = modifiedLayer.filter;
		
		const isUndatedChecked = $('#undated_checkbox').is(':checked');
		
		if (isUndatedChecked) { // Include features within the range AND undated features
		  modifiedLayer.filter = [
		    'all',
		    existingFilter,
		    [
				'any',
				[
				    'all',
				    ['!=', 'max', 'null'],
				    ['!=', 'min', 'null'],
				    ['>=', 'max', dateline.fromValue],
				    ['<=', 'min', dateline.toValue],
				],
				[
					'any',
                    ['==', 'max', 'null'],
                    ['==', 'min', 'null']
				]
			]
		  ];
		} else { // Include features within the range BUT NOT undated features
		  modifiedLayer.filter = [
		    'all',
		    existingFilter,
		    ['has', 'max'],
		    ['has', 'min'],
		    ['>=', 'max', dateline.fromValue],
		    ['<=', 'min', dateline.toValue],
		  ];
		}
		
		return modifiedLayer;
	} else return layer;
}

export function initPopups(mappy, datasetLayers, activePopup, table) {
	
	datasetLayers.forEach(function(layer){
		
		mappy.on('mouseenter', layer.id, function(e) {
	        mappy.getCanvas().style.cursor = 'pointer';
	        
	        var pid = e.features[0].properties.pid;
	        var title = e.features[0].properties.title;
	        var min = e.features[0].properties.min;
	        var max = e.features[0].properties.max;
	
	        if (activePopup) {
	            activePopup.remove();
	        }
	        activePopup = new maptilersdk.Popup({ closeButton: false })
	            .setLngLat(e.lngLat)
	            .setHTML('<b>' + title + '</b><br/>' +
	                'Temporality: ' + (min ? min : '?') + '/' + (max ? max : '?') + '<br/>' +
	                'Click to focus'
	            )
	            .addTo(mappy);
	        activePopup.pid = pid;
	    });

		mappy.on('mousemove', function(e) {
		    if (activePopup) {
		        activePopup.setLngLat(e.lngLat);
		    }
		});

		mappy.on('mouseleave', layer.id, function() {
			mappy.getCanvas().style.cursor = '';
		    if (activePopup) {
		      activePopup.remove();
		    }
		    
		});

		mappy.on('click', layer.id, function(e) {
			
			var pid;
			if (activePopup && activePopup.pid) {
        		pid = activePopup.pid;
		      	activePopup.remove();
        	} else pid = e.features[0].properties.pid;
		    
		    // Search for the row within the sorted and filtered view
		    var pageInfo = table.page.info();
		    var rowPosition = -1;
			var rows = table.rows({ search: 'applied', order: 'current' }).nodes();
			let selectedRow;
			for (var i = 0; i < rows.length; i++) {
			    var rowData = table.row(rows[i]).data();
			    rowPosition++;
			    if (rowData.properties.pid == pid) {
			        selectedRow = rows[i];
			        break; // Stop the loop when the row is found
			    }
			}

		    if (rowPosition !== -1) {
		        // Calculate the page number based on the row's position
		        var pageNumber = Math.floor(rowPosition / pageInfo.length);
		        console.log(`Feature ${pid} selected at table row ${rowPosition} on page ${pageNumber + 1} (current page ${pageInfo.page + 1}).`);
		        
		        // Check if the row is on the current page
		        if (pageInfo.page !== pageNumber) {
		            table.page(pageNumber).draw('page');
		        }
		
		        selectedRow.scrollIntoView();
		        $(selectedRow).trigger('click');
		    }
			
		})
		
	});	
}
