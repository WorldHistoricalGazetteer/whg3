import { envelope } from './6.5.0_turf.min.js'
import { getPlace } from './getPlace';
import { startSpinner } from './utilities';

function highlightFirstRow() {
	$("#placetable tr").removeClass("highlight-row");
	const row = $("#ds_table table tbody")[0].rows[0]
	const pid = parseInt(row.cells[0].textContent)
	// highlight first row, fetch detail, but don't zoomTo() it
	$("#placetable tbody").find('tr').eq(0).addClass('highlight-row')
	getPlace(pid)
}

// Adjust the DataTable's page length to avoid scrolling where possible
function adjustPageLength() {
    const dsTable = document.getElementById('ds_table');
    const tableFilter = document.getElementById('placetable_filter');
    const tablePaginate = document.getElementById('placetable_paginate');
    const theadRow = document.querySelector('#placetable thead tr');
    const tbody = document.querySelector('#placetable tbody');
    const availableHeight = dsTable.clientHeight - (2 * 10 /*padding*/) - tableFilter.clientHeight - tablePaginate.clientHeight - theadRow.clientHeight;
    const averageRowHeight = 2 + ( tbody.clientHeight / document.querySelectorAll('#placetable tr:not(thead tr)').length );
    let estimatedRowsPerPage = Math.floor(availableHeight / ( averageRowHeight ));
  	// Ensure a minimum of 5 rows
  	estimatedRowsPerPage = Math.max(estimatedRowsPerPage, 5);
	console.log(`Changing table length to ${estimatedRowsPerPage} rows @${averageRowHeight} pixels.`);
  	const DataTable = $('#placetable').DataTable();
  	DataTable.page.len(estimatedRowsPerPage).draw();
}

export function resetSearch() {
	var e = $.Event('keyup')
	e.which(13)
	$("#placetable_filter input").trigger(e)
}

export function filterColumn(i, v) {
	// clear then search
	table
		.columns([1])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}

export function clearFilters() {
	// clear
	table
		.columns([1])
		.search('')
		.draw();
	$("#status_select").val('99')
}

export function highlightFeature(pid, highlightedFeatureIndex, features, mappy, mapBounds, mapPadding) {
	
	var featureIndex = features.findIndex(f => f.properties.pid === parseInt(pid)); // .addSource 'generateId': true doesn't create a findable .id property
	if (featureIndex !== -1) {
		console.log('highlightedFeatureIndex',highlightedFeatureIndex);
		if (highlightedFeatureIndex !== undefined) mappy.setFeatureState({ source: 'places', id: highlightedFeatureIndex }, { highlight: false });
	    var feature = features[featureIndex];
		const geom = feature.geometry;
		if (geom) {
			const coords = geom.coordinates;
			highlightedFeatureIndex = featureIndex;
			mappy.setFeatureState({ source: 'places', id: featureIndex }, { highlight: true });
			
			// zoom to feature
			if (geom.type.toLowerCase() == 'point') {
				const flycoords = typeof(coords[0]) == 'number' ? coords : coords[0]
				const mapBounds = {
					'center': flycoords,
					'zoom': 7
				}
				mappy.flyTo({
					...mapBounds,
					padding: mapPadding
				})
			} else {
				mapBounds = envelope(geom).bbox
				mappy.fitBounds(mapBounds, {
					padding: mapPadding
				})
			}
		}
		else {
			console.log('Feature in clicked row has no geometry.');
		}
	} else {
	    console.log(`Feature ${pid} not found.`);
	}
	
	return highlightedFeatureIndex;
	
}

export function initialiseTable(features, checked_rows, spinner_table, spinner_detail) {
	
	console.log('initialiseTable', features);
	
	// START ds_info controls
	var isCollapsed = localStorage.getItem('isCollapsed') === 'true';

	// Set initial height and icon
	if (isCollapsed) {
		$('#ds_info').css('height', '40px');
		$('#expandIcon').show();
		$('#collapseIcon').hide();
		$('#iconLabel').text('Show Detail');
	}

	$('#toggleIcon').click(function() {
		if (isCollapsed) {
			// if the div is collapsed, expand it to fit its content
			$('#ds_info').css('height', 'fit-content');
			$('#expandIcon').hide();
			$('#collapseIcon').show();
			$('#iconLabel').text('Hide');
			isCollapsed = false;
		} else {
			// if the div is not collapsed, animate it to 40px height
			$('#ds_info').css('height', '40px');
			$('#expandIcon').show();
			$('#collapseIcon').hide();
			$('#iconLabel').text('Show Detail');
			isCollapsed = true;
		}

		// Store the state in local storage
		localStorage.setItem('isCollapsed', isCollapsed);
	});

	// Update the state when the checkbox is checked
	$('#checkbox').change(function() {
		localStorage.setItem('isCollapsed', $(this).is(':checked'));
	});
	// END ds_info controls

	checked_rows = []
	localStorage.setItem('filter', '99')
	var wdtask = false
	var tgntask = false
	var whgtask = false

	const check_column = window.loggedin == true ? {
		data: "properties.pid",
      	render: function (data, type, row) {
        	return `<input type="checkbox" name="addme" class="table-chk" data-id="${data}"/>`;
      	},
	} : {
		"data": "properties.pid",
		"visible": false
	}

	spinner_table = startSpinner("drftable_list");
	spinner_detail = startSpinner("row_detail");

	// task columns are inoperable in this public view
	const table = $('#placetable').DataTable({
		/*dom:  "<'row small'<'col-sm-12 col-md-4'l>"+*/
		dom: "<'row small'<'col-sm-7'f>" +
			"<'col-sm-5'>>" +
			"<'row'<'col-sm-12'tr>>" +
			"<'row small'<'col-sm-12'p>>",
		// scrollY: 400,
		select: true,
		order: [
			[0, 'asc']
		],
		//pageLength: 250,
		//LengthMenu: [25, 50, 100],
		data: features,
		columns: [
			{
		      data: "properties.pid",
		      render: function (data, type, row) {
		        return `<a href="http://localhost:8000//api/db/?id=${data}" target="_blank">${data}</a>`;
		      }
		    },
		    {
		      data: "properties.title"
		    },
		    {
				data: "geometry",
	            render: function (data, type, row) {
	                if (data) {
	                    return `<img src="/static/images/geo_${data.type.toLowerCase().replace('multi','')}.svg" width=12/>`;
	                } else {
	                    return "<i>none</i>";
	                }
	            }
		    },
		    check_column
		],
		columnDefs: [
			/*{ className: "browse-task-col", "targets": [8,9,10] },*/
			/*{ orderable: false, "targets": [4, 5]},*/
			{
				orderable: false,
				"targets": [0, 2, 3]
			},
			{
				searchable: false,
				"targets": [0, 2, 3]
			}
			/*, {visible: false, "targets": [5]}*/
			/*, {visible: false, "targets": [0]}*/
		],
		rowId: 'properties.pid',
	    createdRow: function (row, data, dataIndex) {
	        // Attach temporal min and max properties as data attributes
	        $(row).attr('data-min', data.properties.min);
	        $(row).attr('data-max', data.properties.max);
			if (!data.geometry) {
		        $(row).addClass('no-geometry');
		    }
			if (data.properties.min === 'null' || data.properties.max === 'null') {
		        $(row).addClass('no-temporal');
		    }
	    },
	    initComplete: function(settings, json) {
	        adjustPageLength();
	    },
	    drawCallback: function(settings) {
			console.log('table drawn')
			spinner_table.stop()
			// recheck inputs in checked_rows
			if (checked_rows.length > 0) {
				for (i in checked_rows) {
					$('[data-id=' + checked_rows[i] + ']').prop('checked', true)
				}
				// make sure selection_status is visible
				$("#selection_status").show()
			}
			highlightFirstRow();
	    }
	})

	$("#addchecked").click(function() {
		console.log('clicked #addchecked')
		$("#addtocoll_popup").fadeIn()
	})

	$(".closer").click(function() {
		$("#addtocoll_popup").hide()
	})

	// help popups
	$(".help-matches").click(function() {
		page = $(this).data('id')
		console.log('help:', page)
		$('.selector').dialog('open');
	})

	$(".table-chk").click(function(e) {
		e.preventDefault()
		console.log('adding', $(this).data('id'))
		/*console.log('checked_rows',checked_rows)*/
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
	
	return {table, checked_rows}
}