// /whg/webpack/js/ds_browse.js

import { startSpinner } from './utilities';
import { getPlace } from './getPlace';

import '../css/ds_browse.css';

let mappy = new whg_maplibre.Map({
	maxZoom: 10
});

let featureCollection;
let highlightedFeatureId = false;

let table;

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');	
			
			renderData(window.ds_list[0]['id'])
			
			mappy.getContainer().style.opacity = 1;
            
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => resolve());
    });
}

Promise.all([waitMapLoad(), waitDocumentReady(), Promise.all(datatables_CDN_fallbacks.map(loadResource))])
    .then(() => {
		
		console.log(`wdtask: ${wdtask}, tgntask: ${tgntask}, whgtask: ${whgtask}, anytask: ${anytask}`);
	  	
		localStorage.setItem('filter', '99')
		// hide filter dropdown if there are no tasks
		const filter_col = anytask ? "<'#status_filter.col-sm-12 col-md-5'>" : "<'#nostatus.col-sm-12 col-md-5'>";
		
		buildSelect();
		const spinner_table = startSpinner("drftable_list");
		
		table = $('#placetable').DataTable({
			dom: "<'row'<'col-sm-12 col-md-3'l>+" +
				filter_col +
				"<'col-sm-12 col-md-4'f>>" +
				"<'row'<'col-sm-12'tr>>" +
				"<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
			serverSide: true,
			ajax: {
				url: `/api/placetable/?format=datatables&ds=${dslabel}`
			},
			scrollY: 400,
			select: true,
			order: [
				[2, 'asc']
			],
			columns: [{
					"data": "id"
				},
				{
					"data": "src_id"
				},
				{
					"data": "title"
				},
				{
					"data": "ccodes"
				},
				{
					"data": "geo"
				},
				{
					"data": "review_wd"
				},
				{
					"data": "review_tgn"
				},
				{
					"data": "review_whg"
				},
				{
					"data": "revwd",
					"visible": wdtask ? true : false,
					"orderable": false
				},
				{
					"data": "revtgn",
					"visible": tgntask ? true : false,
					"orderable": false
				},
				{
					"data": "revwhg",
					"visible": whgtask ? true : false,
					"orderable": false
				}
			],
			columnDefs: [{
					className: "browse-task-col",
					"targets": [8, 9, 10]
				},
				{
					orderable: false,
					"targets": [4, 5, 6, 7]
				},
				{
					searchable: false,
					"targets": [0, 1, 3, 4, 8, 9, 10]
				}, {
					visible: false,
					"targets": [5, 6, 7]
				}
			],
			initComplete: function(settings, json) {
			},
			drawCallback: function(settings) {
				$("#status_filter").html(buildSelect());
				$("#status_select").val(localStorage.getItem('filter'))
				spinner_table.stop()
				setRowEvents();
			}
			
		})
		
		let activePopup;

		function clearPopup(preserveCursor = false) {
			if (activePopup) {
				activePopup.remove();
				activePopup = null;
				if (!preserveCursor) mappy.getCanvas().style.cursor = '';
			}
		}
		
		mappy.on('mouseleave', function() { clearPopup() }); // Cursor might slide off both map and a large feature
		
		mappy.on('click', function() {
			if (activePopup) {
				getPlace(activePopup.pid);
				clearPopup();
				$('.highlight-row, .selected').removeClass('highlight-row selected');
			}
		});
		
		mappy.on('mousemove', function(e) {

			const features = mappy.queryRenderedFeatures(e.point);
			if (features.length > 0) {
				const topFeature = features[0]; // Handle only the top-most feature
				const isAddedFeature = !mappy.baseStyle.layers.includes(topFeature.layer.id);
				if (isAddedFeature) {
					mappy.getCanvas().style.cursor = 'pointer';
					var coordinates = [e.lngLat.lng, e.lngLat.lat];
					var props = topFeature.properties
					console.log(props);
					if (!!featureCollection.tilesets) {
						props = featureCollection.features.find(feature => feature.properties && feature.properties.pid === props.pid).properties;
					}
					var pid = props.pid;
					var title = props.title;
					var min = props.min;
					var max = props.max;
					var src_id = props.src_id; // Unused
					var fc = props.fclasses; // Unused
					/* At low zoom levels, show popup only at +/-180 degrees longitude */
					coordinates[0] = ((coordinates[0] - e.lngLat.lng + 180) % 360 + 360) % 360 - 180;
					var html = `<b>${ title }</b>`;
					if (min !== null && min !== 'null' && min !== undefined) {
						html += `<br/>earliest: ${min}<br/>latest: ${max}`;
					}
					html += '<br/>[click to fetch details]';
					if (!activePopup || activePopup.pid !== topFeature.properties.pid) {
						if (activePopup) {
							clearPopup(true);
						}
						activePopup = new whg_maplibre.Popup({
								closeButton: false,
							})
							.setLngLat(coordinates)
							.setHTML(html)
							.addTo(mappy);
						activePopup.pid = topFeature.properties.pid;
					} else { // move it
						activePopup.setLngLat(e.lngLat);
					}

				} else {
					clearPopup();
				}
			} else {
				clearPopup();
			}
		});	
		
    })
    .catch(error => console.error("An error occurred:", error));

function highlightFeature(ds_pid, features, mappy, extent=false) { //TODO: This has *similar* functionality to the same-named function in tableFunctions - refactor?
	
	console.log('ds_pid', ds_pid);

	var featureIndex = features.findIndex(f => f.properties.pid === parseInt(ds_pid.pid));
	if (featureIndex !== -1) {
		if (window.highlightedFeatureIndex !== undefined) mappy.setFeatureState(window.highlightedFeatureIndex, {
			highlight: false
		});
		var feature = features[featureIndex];
		const geom = feature.geometry;
		if (geom) {
			const coords = geom.coordinates;
			window.highlightedFeatureIndex = {
				source: ds_pid.ds_id,
				sourceLayer: mappy.getSource(ds_pid.ds_id).type == 'vector' ? 'features' : '',
				id: featureIndex
			};
			mappy.setFeatureState(window.highlightedFeatureIndex, {
				highlight: true
			});
			// zoom to feature
			if (extent) {
				mappy.fitViewport(extent);
			}
			else if (geom.type.toLowerCase() == 'point') {
				const flycoords = typeof(coords[0]) == 'number' ? coords : coords[0];
				mappy.flyTo({
					'center': flycoords,
					'zoom': 7,
					'duration': duration
				})
			} else {
				mappy.fitViewport(bbox(geom));
			}
		} else {
			console.log('Feature in clicked row has no geometry.');
		}
	} else {
		console.log(`Feature ${ds_pid.pid} not found.`);
	}

}
    

function setRowEvents() {
	$("#status_select").change(function(e) {
		// clear search first
		console.log('search has val:', $("#placetable_filter input").val())
		//$("#placetable_filter input").val('')
		if ($("#placetable_filter input").val() != '') {
			$('#placetable').DataTable().search('').draw()
		}
		//fnDraw()
		const val = $(this).val();
		localStorage.setItem('filter', val);
		console.log(val);
		const spinner_filter = startSpinner("status_filter");
		if (val == '99') {
			// clear search
			clearFilters();
		} else {
			clearFilters();
			filterColumn(val[0], val[1]);
		}
		spinner_filter.stop();
	})

	$("#placetable tbody tr").click(function() {
		const thisy = $(this);
		// close popup if exists
		if (typeof poppy != 'undefined') {
			poppy.remove();
		}
		// get id
		const pid = parseInt( $(this)[0].cells[0].textContent );

		// highlight this row, clear others
		var selected = $(this).hasClass("highlight-row");
		$("#placetable tr").removeClass("highlight-row");

		if (!selected)
			$(this).removeClass("rowhover");
		$(this).addClass("highlight-row");

		// fetch its detail
		getPlace(pid, false, false, function(placedata) {
		    console.log('placedata', placedata);
	
			const ds_pid = {
				ds: featureCollection.ds,
				pid: pid,
				ds_id: featureCollection.ds_id
			}
		    
		    highlightFeature(ds_pid, featureCollection.features, mappy, placedata.extent);
		   
		});

	})

	const row = $("#drftable_list table tbody")[0].rows[0];
	const pid = parseInt(row.cells[0].textContent);
	// highlight first row, fetch detail, but don't zoomTo() it
	$("#placetable tbody").find('tr').eq(0).addClass('highlight-row');

	if (pid) {
		const spinner_detail = startSpinner("row_detail");
		getPlace(pid);
		spinner_detail.stop();
	}
	
	// help popups
	$(".help-matches").click(function() {
		page = $(this).data('id')
		console.log('help:', page)
		$('.selector').dialog('open');
	})
	$(".selector").dialog({
		resizable: false,
		autoOpen: false,
		height: 500,
		width: 700,
		title: "WHG Help",
		modal: true,
		buttons: {
			'Close': function() {
				console.log('close dialog');
				$(this).dialog('close');
			}
		},
		open: function(event, ui) {
			$('#helpme').load('/media/help/' + page + '.html')
		},
		show: {
			effect: "fade",
			duration: 400
		},
		hide: {
			effect: "fade",
			duration: 400
		}
	});	
	
}    
    
// fetch and render
function renderData(dsid) {
        		
    fetch(`/datasets/${ dsid }/mapdata/`)
        .then((response) => {
            if (!response.ok) {
                throw new Error('Failed to fetch dataset GeoJSON.');
            }
            return response.json(); // Parse the response JSON
        })
        .then((data) => {
            console.log('Fetched data.', data);
			data.ds = dsid;
			data.ds_id = `datasets_${ dsid }`;
			
            mappy
			.newSource(data)
			.newLayerset(data.ds_id);
			
			mappy.fitViewport( data.extent || bbox( data ), {
				padding: 30
			})
			
            featureCollection = data; // Set the global variable
        })
        .catch((error) => {
            console.error(error);
        });
        
}

function buildSelect() {
	var select = '<label>Review filters: <select name="status" aria-controls="placetable" id="status_select" class="datatables_length">' +
		'<option value="99" selected="selected">All</option>'

	if (wdtask) {
		select +=
			'<option disabled>-----wikidata-----</option>' +
			'<option value="50">Needs review (wd)</option>' +
			'<option value="51">Reviewed (wd)</option>' +
			'<option value="52">Deferred (wd)</option>'
	}
	if (tgntask) {
		select +=
			'<option disabled>-------tgn-------</option>' +
			'<option value="60">Needs review (tgn)</option>' +
			'<option value="61">Reviewed (tgn)</option>' +
			'<option value="62">Deferred (tgn)</option>'
	}
	if (whgtask) {
		select +=
			'<option disabled>-------whg-------</option>' +
			'<option value="70">Needs review (whg)</option>' +
			'<option value="71">Reviewed (whg)</option>' +
			'<option value="72">Deferred (whg)</option>'
	}

	select += '</select></label>'
	return select
}

function filterColumn(i, v) {
	// clear then search
	console.log('filterColumn', i, v, typeof(i))
	table
		.columns([7, 8])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}

function clearFilters() {
	// clear
	table
		.columns([5, 6, 7])
		.search('')
		.draw();
	$("#status_select").val('99')
}