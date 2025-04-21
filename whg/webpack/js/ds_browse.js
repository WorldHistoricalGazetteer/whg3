// /whg/webpack/js/ds_browse.js

import {getPlace} from './getPlace';
import '../css/ds_browse.css';

let whg_map = new whg_maplibre.Map({maxZoom: 10});
let featureCollection;
let table;
let activePopup;
let highlightedFeatureId = false;

async function init() {
    await waitMapLoad();
    await waitDocumentReady();
    await Promise.all(datatables_CDN_fallbacks.map(loadResource));

    console.log(`wdtask: ${wdtask}, tgntask: ${tgntask}, whgtask: ${whgtask}, anytask: ${anytask}`);

    localStorage.setItem('filter', '99');

    const filter_col = anytask ? "<'#status_filter.col-sm-12 col-md-5'>" : "<'#nostatus.col-sm-12 col-md-5'>";

    try {
        const response = await fetch(mapdata_url);
        if (!response.ok) throw new Error(`Failed to load mapdata: ${response.status}`);
        window.datacollection = await response.json();

        featureCollection = window.datacollection.table;

        // whg_map
        //     .newSource(window.datacollection.points)
        //     .newLayerset(window.datacollection.metadata.ds_id);
        whg_map.fitViewport(window.datacollection.metadata.extent, defaultZoom);

        initPlacetable(filter_col);
        initMapInteractions();
        whg_map.getContainer().style.opacity = 1;

    } catch (error) {
        console.error("Error loading mapdata:", error);
    }
}

function waitMapLoad() {
    return new Promise(resolve => {
        whg_map.on('load', () => {
            console.log('Map loaded.');
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise(resolve => {
        $(document).ready(resolve);
    });
}

init();

function initPlacetable(filter_col) {
    $('#drftable_list').spin();

	const data = featureCollection.features.map(f => {
		const props = f.properties || {};
		return {
			id: props.pid || props.id,
			src_id: props.src_id || '',
			title: props.title || '',
			ccodes: props.ccodes || '',
			geo: props.geo || '',
			review_wd: props.review_wd || '',
			review_tgn: props.review_tgn || '',
			review_whg: props.review_whg || '',
			revwd: props.review_wd ? props.review_wd : '<i>no hits</i>',
			revtgn: props.review_tgn ? props.review_tgn : '<i>no hits</i>',
			revwhg: props.review_whg ? props.review_whg : '<i>no hits</i>'
		};
	});

    table = $('#placetable').DataTable({
        dom: "<'row'<'col-sm-12 col-md-3'l>" + filter_col + "<'col-sm-12 col-md-4'f>>" +
            "<'row'<'col-sm-12'tr>>" +
            "<'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>",
        serverSide: false,
        data: data,
        scrollY: 400,
        select: true,
        order: [[2, 'asc']],
        columns: [
            {"data": "id"},
            {"data": "src_id"},
            {"data": "title"},
            {"data": "ccodes"},
            {"data": "geo"},
            {"data": "review_wd"},
            {"data": "review_tgn"},
            {"data": "review_whg"},
            {"data": "revwd", "visible": !!wdtask, "orderable": false},
            {"data": "revtgn", "visible": !!tgntask, "orderable": false},
            {"data": "revwhg", "visible": !!whgtask, "orderable": false}
        ],
        columnDefs: [
            {className: "browse-task-col", "targets": [8, 9, 10]},
            {orderable: false, "targets": [4, 5, 6, 7]},
            {searchable: false, "targets": [0, 1, 3, 4, 8, 9, 10]},
            {visible: false, "targets": [5, 6, 7]}
        ],
        drawCallback: () => {
            $("#status_filter").html(buildSelect());
            $("#status_select").val(localStorage.getItem('filter'));
            setRowEvents();
        },
		initComplete: () => {
			$('#drftable_list').stopSpin();
		}
    });
}

function initMapInteractions() {
    whg_map.on('mouseleave', () => clearPopup());

    whg_map.on('click', () => {
        if (activePopup) {
            getPlace(activePopup.pid);
            clearPopup();
            $('.highlight-row, .selected').removeClass('highlight-row selected');
        }
    });

    whg_map.on('mousemove', e => {
        const features = whg_map.queryRenderedFeatures(e.point);
        if (!features.length) return clearPopup();

        const topFeature = features[0];
        const isAddedFeature = !whg_map.baseStyle.layers.includes(topFeature.layer.id);
        if (!isAddedFeature) return clearPopup();

        whg_map.getCanvas().style.cursor = 'pointer';

        let props = topFeature.properties;
        if (!!featureCollection.tilesets) {
            props = featureCollection.features.find(f => f.properties?.pid === props.pid)?.properties;
        }

        if (!props) return clearPopup();

        const coordinates = [(e.lngLat.lng + 540) % 360 - 180, e.lngLat.lat];
        let html = `<b>${props.title}</b>`;
        if (props.min && props.min !== 'null') {
            html += `<br/>earliest: ${props.min}<br/>latest: ${props.max}`;
        }
        html += '<br/>[click to fetch details]';

        if (!activePopup || activePopup.pid !== props.pid) {
            clearPopup(true);
            activePopup = new whg_maplibre.Popup({closeButton: false})
                .setLngLat(coordinates)
                .setHTML(html)
                .addTo(whg_map);
            activePopup.pid = props.pid;
        } else {
            activePopup.setLngLat(e.lngLat);
        }
    });
}

function clearPopup(preserveCursor = false) {
    if (activePopup) {
        activePopup.remove();
        activePopup = null;
        if (!preserveCursor) {
            whg_map.getCanvas().style.cursor = '';
        }
    }
}

function highlightFeature(ds_pid, features, whg_map, extent = false) { //TODO: This has *similar* functionality to the same-named function in tableFunctions - refactor?

    console.log('ds_pid', ds_pid);

    var featureIndex = features.findIndex(f => f.properties.pid === parseInt(ds_pid.pid));
    if (featureIndex !== -1) {
        if (window.highlightedFeatureIndex !== undefined) whg_map.setFeatureState(window.highlightedFeatureIndex, {
            highlight: false
        });
        var feature = features[featureIndex];
        const geom = feature.geometry;
        if (geom) {
            const coords = geom.coordinates;
            window.highlightedFeatureIndex = {
                source: ds_pid.ds_id,
                sourceLayer: whg_map.getSource(ds_pid.ds_id).type == 'vector' ? 'features' : '',
                id: featureIndex
            };
            whg_map
                .fitViewport(extent || bbox(geom), defaultZoom)
                .setFeatureState(window.highlightedFeatureIndex, {
                    highlight: true
                });
        } else {
            console.log('Feature in clicked row has no geometry.');
        }
    } else {
        console.log(`Feature ${ds_pid.pid} not found.`);
    }

}

function setRowEvents() {
    $("#status_select").change(function (e) {
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
        $('#status_filter').spin();
        if (val == '99') {
            // clear search
            clearFilters();
        } else {
            clearFilters();
            filterColumn(val[0], val[1]);
        }
        $('#status_filter').stopSpin();
    })

    $("#placetable tbody tr").click(function () {
        const thisy = $(this);
        // close popup if exists
        if (typeof poppy != 'undefined') {
            poppy.remove();
        }
        // get id
        const pid = parseInt($(this)[0].cells[0].textContent);

        // highlight this row, clear others
        var selected = $(this).hasClass("highlight-row");
        $("#placetable tr").removeClass("highlight-row");

        if (!selected)
            $(this).removeClass("rowhover");
        $(this).addClass("highlight-row");

        // fetch its detail
        getPlace(pid, false, function (placedata) {
            console.log('placedata', placedata);

            const ds_pid = {
                ds: featureCollection.ds,
                pid: pid,
                ds_id: featureCollection.ds_id
            }

            highlightFeature(ds_pid, featureCollection.features, whg_map, placedata.extent);

        });

    })

    const row = $("#drftable_list table tbody")[0].rows[0];
    const pid = parseInt(row.cells[0].textContent);
    // highlight first row, fetch detail, but don't zoomTo() it
    $("#placetable tbody").find('tr').eq(0).addClass('highlight-row');

    if (pid) {
        $('#row_detail').spin();
        getPlace(pid);
        $('#row_detail').stopSpin();
    }

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
    console.log('filterColumn', i, v, typeof (i))
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