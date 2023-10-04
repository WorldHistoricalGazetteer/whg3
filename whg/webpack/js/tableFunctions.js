import { envelope } from './6.5.0_turf.min.js';
import { getPlace } from './getPlace';
import { startSpinner } from './utilities';
import { updatePadding, recenterMap/*, logSourcesAndLayers*/ } from './mapFunctions';
import datasetLayers from './mapLayerStyles';
import { mapSequencer } from './mapControls';
import { mappy } from './mapAndTable';

let table;

function highlightFirstRow() {
	$("#placetable tr").removeClass("highlight-row");
	const firstrow = $("#placetable tbody tr:first");
	const pid = firstrow.data('ds_pid').pid;
	const cid = firstrow.data('cid');
	// highlight first row and fetch detail, but don't fly map to it
	firstrow.addClass('highlight-row');
	getPlace(pid, cid);
}

// Adjust the DataTable's page length to avoid scrolling where possible
function adjustPageLength() {
	const dsTable = document.getElementById('ds_table');
	const tableFilter = document.getElementById('placetable_filter');
	const tablePaginate = document.getElementById('placetable_paginate');
	const theadRow = document.querySelector('#placetable thead tr');
	const tbody = document.querySelector('#placetable tbody');
	const availableHeight = dsTable.clientHeight - (2 * 10 /*padding*/ ) - tableFilter.clientHeight - tablePaginate.clientHeight - theadRow.clientHeight;
	const averageRowHeight = 2 + (tbody.clientHeight / document.querySelectorAll('#placetable tr:not(thead tr)').length);
	let estimatedRowsPerPage = Math.floor(availableHeight / (averageRowHeight));
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

function filterColumn(i, v) {
	// clear then search
	table
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#ds_select").val(localStorage.getItem('filter'))
}

function clearFilters() {
	// clear
	table
		.columns([3, 5, 6, 7, 11]) // TODO: Check these values?
		.search('')
		.draw();
	$("#ds_select").val('-1')
}

// TODO: ? Remove this version, which was apparently redundant in ds_places ?
/*export function filterColumn(i, v) {
	// clear then search
	table
		.columns([1])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}*/

//  TODO: ? Remove this version, which was apparently redundant in ds_places ?
/*export function clearFilters() {
	// clear
	table
		.columns([1])
		.search('')
		.draw();
	$("#status_select").val('99')
}*/

function toggleMapLayers(mappy, val) {
	let recentered = false;
	datasetLayers.forEach(function(layer) {
		window.ds_list.forEach(function(ds) {
			mappy.setLayoutProperty(`${layer.id}_${ds.id}`, 'visibility', (val == 'all' || ds.id.toString() === val.toString()) ? 'visible' : 'none');
			if (!recentered && ds.id.toString() === val.toString()) {
				recentered = true;
				window.mapBounds = ds.extent;
				recenterMap('lazy');
			}
		});
	});
}

export function scrollToRowByProperty(table, propertyName, value) {
    // Search for the row within the sorted and filtered view
    var pageInfo = table.page.info();
    var rowPosition = -1;
    var rows = table.rows({
        search: 'applied',
        order: 'current'
    }).nodes();
    let selectedRow;
    for (var i = 0; i < rows.length; i++) {
        var rowData = table.row(rows[i]).data();
        rowPosition++;
        if (rowData.properties[propertyName] == value) {
            selectedRow = rows[i];
            break; // Stop the loop when the row is found
        }
    }

    if (rowPosition !== -1) {
        // Calculate the page number based on the row's position
        var pageNumber = Math.floor(rowPosition / pageInfo.length);

        // Check if the row is on the current page
        if (pageInfo.page !== pageNumber) {
            table.page(pageNumber).draw('page');
        }

        selectedRow.scrollIntoView();
        $(selectedRow).trigger('click');
    }
}

export function highlightFeature(ds_pid, features, mappy) {

	//logSourcesAndLayers();

	features = features.filter(f => f.properties.dsid === ds_pid.ds);

	var featureIndex = features.findIndex(f => f.properties.pid === parseInt(ds_pid.pid));
	if (featureIndex !== -1) {
		//console.log(`Switching highlight from ${window.highlightedFeatureIndex} to ${featureIndex}.`);
		if (window.highlightedFeatureIndex !== undefined) mappy.setFeatureState(window.highlightedFeatureIndex, {
			highlight: false
		});
		var feature = features[featureIndex];
		const geom = feature.geometry;
		if (geom) {
			const coords = geom.coordinates;
			window.highlightedFeatureIndex = {
				source: ds_pid.ds.toString(),
				id: featureIndex
			};
			mappy.setFeatureState(window.highlightedFeatureIndex, {
				highlight: true
			});
			updatePadding();
			// zoom to feature
			if (geom.type.toLowerCase() == 'point') {
				const flycoords = typeof(coords[0]) == 'number' ? coords : coords[0]
				window.mapBounds = {
					'center': flycoords,
					'zoom': 7
				}
				recenterMap('lazy');
			} else {
				window.mapBounds = envelope(geom).bbox;
				recenterMap('lazy');
			}
			//console.log(`Highlight now on ${window.highlightedFeatureIndex}.`);
		} else {
			console.log('Feature in clicked row has no geometry.');
		}
	} else {
		console.log(`Feature ${ds_pid.pid} not found.`);
	}

}

export function initialiseTable(features, checked_rows, spinner_table, spinner_detail, mappy) {

	// TODO: remove these artifacts of table used for review
	localStorage.setItem('filter', '99')
	var wdtask = false
	var tgntask = false
	var whgtask = false

	spinner_table = startSpinner("drftable_list");
	spinner_detail = startSpinner("row_detail");

	const isCollection = window.ds_list[0].ds_type == 'collections';

	checked_rows = []

	if (window.ds_list.length > 1) { // Initialise dataset selector
		let select = '<label>Datasets: <select id="ds_select">' +
			'<option value="-1" data="all" selected="selected">All</option>';
		for (let ds of window.ds_list) {
			select += '<option value="' + ds.label + '" data="' + ds.id + '">' +
				ds.title + '</option>'
		}
		select += '</select></label>';
		$("#ds_filter").html(select);
	}

	// Define Datatable columns based on ds_type
	let columns;
	let columnDefs;
	let order;
	if (!isCollection) { // Datasets

		const check_column = window.loggedin ? {
            title: "<a href='#' rel='tooltip' title='add one or more rows to a collection'><i class='fas fa-question-circle linkypop'></i></a>",
			data: "properties.pid",
			render: function(data, type, row) {
				return `<input type="checkbox" name="addme" class="table-chk" data-id="${data}"/>`;
			},
			visible: true
		} : {
			data: "properties.pid",
			visible: false
		}

		columns = [{
                title: "pid",
				data: "properties.pid",
				render: function(data, type, row) {
					return `<a href="http://localhost:8000//api/db/?id=${data}" target="_blank">${data}</a>`;
				}
			},
			{
                title: "title",
				data: "properties.title"
			},
			{
                title: "geo",
				data: "geometry",
				render: function(data, type, row) {
					if (data) {
						return `<img src="/static/images/geo_${data.type.toLowerCase().replace('multi', '')}.svg" width=12/>`;
					} else {
						return "<i>none</i>";
					}
				}
			},
			{
                title: "dataset",
				data: function(row) {
					return row.properties.dslabel || null;
				}
			},
			check_column
		];
		
		columnDefs = [{
				orderable: false,
				"targets": [0, 2, 4]
			},
			{
				searchable: false,
				"targets": [0, 2, 4]
			},
			{
				visible: window.ds_list.length > 1,
				"targets": [3]
			}
		];
		
		order = [
			[1, 'asc']
		];
	} else { // Collections
		columns = [{
                title: "seq",
                data: "properties.seq"
            }, {
                title: "title",
                data: "properties.title"
            }, {
                title: "country",
                data: "properties.ccodes"
            }, {
                data: "properties.pid"
            }
        ];
            
		columnDefs = [{
				orderable: false,
				"targets": []
			},{
                searchable: false,
                "targets": [2]
            },{
                visible: false,
                "targets": [3]
            }
        ];
		
		order = [
			[0, 'asc']
		];
	}

	table = $('#placetable').DataTable({
		dom: "<'row small'<'col-sm-7'f>" +
			"<'col-sm-5'>>" +
			"<'row'<'col-sm-12'tr>>" +
			"<'row small'<'col-sm-12'p>>",
		select: true,
		columns: columns,
		columnDefs: columnDefs,
		order: order,
		data: features,
		rowId: 'properties.pid',
		createdRow: function(row, data, dataIndex) {
			// Attach temporal min and max properties as data attributes
			$(row).attr('data-min', data.properties.min);
			$(row).attr('data-max', data.properties.max);
			$(row).attr('dsid', data.properties.dsid);
			$(row).attr('pid', data.properties.pid);
			$(row).data('ds_pid', {
				ds: data.properties.dsid,
				pid: data.properties.pid
			});
			$(row).data('cid', data.properties.cid);
			$(row).data('seq', data.properties.seq);
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
			// console.log('table drawn')
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
			if (!!mapSequencer) {
				mapSequencer.updateButtons();
			}
		}
	});

	$("#addchecked").click(function() {
		console.log('clicked #addchecked')
		$("#addtocoll_popup").fadeIn()
	})

	$(".closer").click(function() {
		$("#addtocoll_popup").hide()
	})

	$("#ds_select").change(function(e) {

		// filter table
		let val = $(this).val();
		localStorage.setItem('filter', val)
		window.spinner_map = startSpinner("dataset_content", 3);
		if (val == -1) {
			// clear search
			window.spinner_filter = startSpinner("status_filter");
			clearFilters()
		} else {
			clearFilters()
			filterColumn(3, val)
		}

		// filter map
		let ds_id = $(this).find(":selected").attr("data");
		const dsItem = window.ds_list.find(ds => ds.id === ds_id);
		if (dsItem) {
			window.mapBounds = dsItem.extent;
		}
		else {
			window.mapBounds = window.ds_list_stats.extent;
		}
		toggleMapLayers(mappy, ds_id); // Also recenters map on selected layer
		if (ds_id == 'all') recenterMap('lazy');

		window.spinner_map.stop();
	})

	$("body").on("click", ".table-chk", function(e) {
		// e.preventDefault();
		e.stopPropagation(); // Prevents row-click functionality
		console.log('adding', $(this).data('id'))
		/*console.log('checked_rows',checked_rows)*/
	})

	$("body").on("click", "#placetable tbody tr", function() {
		const ds_pid = $(this).data('ds_pid');

		// highlight this row, clear others
		var selected = $(this).hasClass("highlight-row");
		$("#placetable tr").removeClass("highlight-row");

		if (!selected)
			$(this).removeClass("rowhover");
		$(this).addClass("highlight-row");

		// fetch its detail
		getPlace(ds_pid.pid, $(this).data('cid'), spinner_detail);

		highlightFeature(ds_pid, features, mappy);
		
		if (!!mapSequencer) {
			mapSequencer.updateButtons();
			if (mapSequencer.continuePlay) {
				mapSequencer.continuePlay = false;
			}
			else if (mapSequencer.playing) {
				mapSequencer.stopPlayback();
			}
		}

	});

	// Custom search function to filter table based on dateline.fromValue and dateline.toValue
	$.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {
		if ($('.range_container.expanded').length == 0) { // Is dateline inactive?
			return true;
		}

		const fromValue = window.dateline.fromValue;
		const toValue = window.dateline.toValue;
		const includeUndated = window.dateline.includeUndated

		// Get the min and max values from the data attributes of the row
		const row = $(settings.aoData[dataIndex].nTr);
		const minData = row.attr('data-min');
		const maxData = row.attr('data-max');

		// Convert minData and maxData to numbers for comparison
		const min = minData === 'null' ? 'null' : parseFloat(minData);
		const max = maxData === 'null' ? 'null' : parseFloat(maxData);

		// Filter logic
		if (((!isNaN(fromValue) && !isNaN(toValue)) && (min !== 'null' && max !== 'null' && min <= toValue && max >= fromValue)) || (includeUndated && (min === 'null' || max === 'null'))) {
			return true; // Include row in the result
		}
		return false; // Exclude row from the result
	});

	return {
		table,
		checked_rows
	}
}

export { table };
