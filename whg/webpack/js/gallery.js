// gallery.js

import debounce from 'lodash/debounce';
import {
    fetchDataForHorse,
} from './localGeometryStorage';
import {
    CountryCacheFeatureCollection,
} from './countryCache';

import '../css/gallery.scss';

let mappy = new whg_maplibre.Map({
    style: ['whg-basic-light'],
    maxZoom: 13,
    navigationControl: false,
});

let countryCache = new CountryCacheFeatureCollection();

let page = 1;
const $page_controls = $('#page_controls');
let $select;

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {

            mappy.newSource('countries') // Add empty source
                .newLayerset('countries', 'countries', 'countries');

            console.log('Map loaded.');
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => {
            console.log('Document ready.');
            resolve();
        });
    });
}

function truncateAfterSpace(str, length) {
    if (str === null || str === undefined) {
        return 'not available';
    }
    if (str.length <= length) {
        return str;
    }
    let end = str.indexOf(' ', length);
    if (end === -1) {
        end = length;
    }
    return str.substring(0, end) + '...';
}

function buildGallery(datacollections) {
    const dynamicGallery = $('#dynamic-gallery');
    dynamicGallery.empty();

    if (datacollections.length === 0) {
        const noResultsMessage = $(`
            <h3>No matching ${datacollection} found</h3>
            <p>${$('.nav-link.active').find('input[type="checkbox"]:not(:checked)').length == 3 ?
            'You have not selected any Collection classes.' :
            'Try adjusting the filters.'}</p>
        `);
        dynamicGallery.append(noResultsMessage);
        var layersToRemove = mappy.getStyle().layers.filter(layer => !!layer.source && layer.source == 'featured-data-source');
        layersToRemove.forEach(layer => {
            mappy.removeLayer(layer.id);
        });
        if (mappy.getSource('featured-data-source')) mappy.removeSource('featured-data-source');
        mappy.reset();
    } else {
        datacollections.forEach(dc => {
            const truncatedDescription = truncateAfterSpace(dc.description, 250);
            const dsCard = $(`
	            <div data-bs-toggle="tooltip" data-bs-custom-class="custom-tooltip-red" title="View publication page" class="ds-card-container col-md-4 mt-1">
	              <div class="ds-card-gallery">
	                <div class="ds-card-content">
	                  <span class="float-end">
	                    <button class="btn btn-light btn-sm previewButton" data-bs-toggle="tooltip" data-bs-custom-class="custom-tooltip-green" title="Preview ${dc.label} on map">
	                        <i class="fas ${dc.icon}"></i> Preview
	                    </button>
	                  </span>
	                  <h6 class="ds-card-title strong-red">${dc.title}</h6>
	                  <div class="ds-card-inner">
	                  	<p class="ds-card-creator"><i>Created by</i>: ${dc.authors}</p>
	                    <p class="ds-card-blurb my-1">
	                    	${dc.image_file == null ? '' : `<img src="${dc.image_file}" width="60" class="float-end">`}
	                        ${truncatedDescription}
	                    </p>
	                  <div>
	                </div>
	              </div>
	            </div>
	        `)
                .data({
                    id: dc.ds_or_c_id,
                    type: dc.type,
                    contributors: dc.authors,
                    mode: dc.display_mode,
                    geometry_url: dc.geometry_url,
                    url: dc.url,
                });
            dynamicGallery.append(dsCard);

        });
    }
    $('#dynamic-gallery .previewButton:first').trigger('click');
}

Promise.all([
    waitMapLoad(),
    waitDocumentReady(),
    Promise.all(select2_CDN_fallbacks.map(loadResource)),
]).then(() => {

    const debouncedUpdates = debounce(() => { // Uses imported lodash function
        fetchData();
        updateAreaMap();
    }, 400);

    // Spatial list-entry selector
    const spatialSelector = $('#entrySelector');
    spatialSelector.data('selectedValue', '');
    spatialSelector.prop('disabled', true).select2({
        width: 'element',
        data: [],
        placeholder: '(select dropdown first)',
        allowClear: false,
    }).on('change', function (e) {
        const currentSpatialValue = spatialSelector.val().join(',');
        if (spatialSelector.data('selectedValue') !== currentSpatialValue) {
            debouncedUpdates();
            spatialSelector.data('selectedValue', currentSpatialValue);
        }
    }).parent().tooltip({
        selector: '.select2-container',
        title: function () {
            return $(this).prev().attr('title');
        },
    });

    $('#categorySelector').on('change', function () {
        console.log('#categorySelector', $(this).val());
        spatialSelector.val(null).empty().trigger('change');
        switch ($(this).val()) {
            case 'regions':
                $('#entrySelector').prop('disabled', false).select2({
                    placeholder: 'None',
                    data: dropdown_data[0].children,
                });
                break;
            case 'countries':
                $('#entrySelector').prop('disabled', false).select2({
                    placeholder: 'None',
                    data: dropdown_data[1].children,
                });
                break;
            default:
                $('#entrySelector').prop('disabled', true).select2({
                    placeholder: '(select dropdown first)',
                    data: [],
                });
                break;
        }
    });

    $('#clearButton').on('click', function () {
        spatialSelector.val(null).trigger('change');
    });

    const $checkbox_container = $('<div>', {
        'class': 'checkbox-container',
    });
    // ['Dataset', 'Place', 'Student'].forEach(function(tab_checkbox) {
    ['Dataset', 'Place'].forEach(function (tab_checkbox) {
        const icon = tab_checkbox == 'Dataset' ? 'fa-layer-group' : 'fa-map-pin';
        const labelWithIcon = `${tab_checkbox} <i class="fas ${icon}"></i>`;
        $checkbox_container.append(
            $('<label>', {
                'class': 'checkbox-label',
            }).html(labelWithIcon).prepend($('<input>', {
                'type': 'checkbox',
                'checked': 'checked',
                'disabled': true,
                'name': `${tab_checkbox.toLowerCase()}_checkbox`,
                'id': `${tab_checkbox.toLowerCase()}_checkbox`,
                'title': `Include Collections classed as '${tab_checkbox}'.`,
                'aria-label': `Include Collections classed as '${tab_checkbox}'.`,
                'data-type': tab_checkbox.toLowerCase(),
            })),
        );
    });
    $('#collections-tab').append($checkbox_container);

    [ // description, title, disabled-title, disability test, click-page
        [
            'skip-first',
            'First page',
            '(already at first page of results)',
            'data.current_page == 1',
            '1',
        ],
        [
            'skip-previous',
            'Previous page',
            '(already at first page of results)',
            'data.current_page == 1',
            'data.current_page - 1',
        ],
        [
            'dropbox',
            'Select page',
            '(this is the only page of results)',
            'data.total_pages == 1',
            '',
        ],
        [
            'skip-next',
            'Next page',
            '(already reached last page of results)',
            'data.current_page == data.total_pages',
            'data.current_page + 1',
        ],
        [
            'skip-last',
            'Last page',
            '(already reached last page of results)',
            'data.current_page == data.total_pages',
            'data.total_pages',
        ],
    ].forEach(function (control) {
        const $control = control[0] == 'dropbox' ?
            $('<select>', {
                'title': control[1],
                'aria-label': control[1],
            }) :
            $('<button>', {
                'id': control[0],
                'type': 'button',
                'class': 'btn btn-outline-secondary',
                'style': `background-image: url(/static/images/sequencer/${control[0]}-btn.svg)`,
            });
        $control.data('titles', control.slice(1, 3)).data('disability', control[3]).data('click-page', control[4]).on('click change', function (e) {
            page = $(this).is('button') ? $(this).data('page') : $(this).val();
            if ($(this).is('button') || e.type === 'change') fetchData(page);
        });
        $page_controls.append($control);
    });
    $select = $page_controls.find('select');

    function stateStore(fetch = false) {
        if (fetch) {
            const storedState = sessionStorage.getItem('galleryState');
            if (storedState) {
                const state = JSON.parse(storedState);
                page = state.page;
                $('#reverseSortCheckbox').prop('checked', state.sort.startsWith('-'));
                $('#sortDropdown').val(state.sort.replace(/^-/, ''));
                if (state.regions !== '') {
                    $('#categorySelector').val('regions').trigger('change'); // Loads correct dataset into #entrySelector
                    spatialSelector.val(state.regions.split(',')).trigger('change');
                } else if (state.countries !== '') {
                    $('#categorySelector').val('countries').trigger('change'); // Loads correct dataset into #entrySelector
                    spatialSelector.val(state.countries.split(',')).trigger('change');
                } else $('#categorySelector').val('none').trigger('change');
                $('#searchInput').val(state.search);
            }
            debouncedUpdates();
        } else {
            const spatialSelections = spatialSelector.select2('data');
            const state = {
                page: page,
                sort: ($('#reverseSortCheckbox').prop('checked') ? '-' : '') +
                    ($('#sortDropdown').val() ?? 'title'),
                regions: spatialSelections.some(region => region.ccodes) ?
                    spatialSelections.map(region => region.id).join(',') :
                    '',
                countries: spatialSelections.some(region => region.ccodes) ?
                    '' :
                    spatialSelections.map(country => country.id).join(','),
                search: $('#searchInput').val() ?? '',
            };
            sessionStorage.setItem('galleryState', JSON.stringify(state));
        }
    }

    function fetchData(page = 1) { // Defaults to 1 except when called by page controls
        const classes = $('.checkbox-label input:checked').map(function () {
            return $(this).data('type');
        }).get().join(',');
        const sort = ($('#reverseSortCheckbox').prop('checked') ? '-' : '') +
            ($('#sortDropdown').val() ?? 'title');
        const spatialSelections = spatialSelector.select2('data');
        var countries = spatialSelections.length < 1 ? [] :
            (spatialSelections.some(region => region.ccodes) ?
                [].concat(...spatialSelections.map(region => region.ccodes)) :
                spatialSelections.map(country => country.id));
        countries = countries.join(',');
        const search = $('#searchInput').val() ?? '';
        const url = `/api/gallery/${datacollection}/?page=${page}&classes=${datacollection ==
        'collections' ?
            classes :
            ''}&sort=${sort}&countries=${countries}&q=${search}`;
        console.log(`Fetching from: ${url}`);
        stateStore();
        $('#publications_gallery').spin();
        fetch(url).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        }).then(data => {
            data = data.results;
            console.log('Fetched data:', data);
            buildGallery(data.items);
            $select.empty();
            for (let i = 1; i <= data.total_pages; i++) {
                const $option = $(
                    `<option value=${i}>page ${i} of ${data.total_pages}</option>`).attr('selected', i == data.current_page);
                $select.append($option);
            }
            $page_controls.find('button, select').each(function () {
                const disabled = eval($(this).data('disability'));
                $(this).data('page', eval($(this).data('click-page'))).attr('disabled', disabled).attr('title', $(this).data('titles')[disabled ? 1 : 0]).attr('aria-label', $(this).data('titles')[disabled ? 1 : 0]);
            });
        }).catch(error => {
            console.error('Fetch error:', error);
        })
            .finally(function () {
                $('#publications_gallery').stopSpin();
            });
    }

    stateStore(true); // Fetch and build initial gallery; set map filter

    function updateAreaMap() {
        const spatialSelections = spatialSelector.select2('data');
        const countries = spatialSelections.length < 1 ? [] :
            (spatialSelections.some(region => region.ccodes) ?
                [].concat(...spatialSelections.map(region => region.ccodes)) :
                spatialSelections.map(country => country.id));
        countryCache.filter(countries).then(filteredCountries => {
            mappy.getSource('countries').setData(filteredCountries);

            try {
                mappy.fitBounds(bbox(filteredCountries), {
                    padding: 30,
                    maxZoom: 7,
                    duration: 1000,
                });
            } catch {
                mappy.reset();
            }
        });
    }

    $('a[data-bs-toggle="tab"]').on('shown.bs.tab', function () {
        datacollection = $(this).attr('href').substring(1);
        // Toggle disabled state of place_checkbox and dataset_checkbox
        $('.checkbox-label input').prop('disabled', datacollection !== 'collections');
        fetchData();
    });

    $('.checkbox-container').on('mouseup', function (e) {
        let checkbox_label = $(e.target).closest('.checkbox-label');
        let already_active = $(e.target).closest('.nav-link').hasClass('active');
        if (checkbox_label.length) {
            let checkbox = checkbox_label.find('input');
            checkbox.prop('checked', !checkbox.prop('checked')); // Repair checkbox behaviour suppressed by <a> wrapper
            if (already_active) fetchData(); // Otherwise triggered by Bootstrap tab
        }
    });

    $('#sortDropdown, #reverseSortCheckbox, #searchInput').on('change', function () {
        fetchData();
    });

    $('#searchInput').on('input', function () {
        fetchData();
    });
    $('#clearSearchButton').on('click', function () {
        $('#searchInput').val('');
        fetchData();
    });

    // Observe the map container for size changes: maintain aspect ratio to accommodate all possible bounds
    const mapResizeObserver = new ResizeObserver(entries => {
        mappy._container.style.height = `${Math.round(
            entries[0].contentRect.width * .8)}px`;
        mappy.resize();
    });
    mapResizeObserver.observe(mappy._container);

    // Force country filter to track width of search filter
    const resizeObserver = new ResizeObserver(entries => {
        $('.select2-container').css('width', entries[0].target.offsetWidth);
    });
    resizeObserver.observe($('#searchInput')[0]);

    $('#dynamic-gallery')
        .on('show.bs.tooltip', '.previewButton', (e) => { // Prevent overlapping tooltips
            const instance = bootstrap.Tooltip.getInstance($(e.target).closest('.ds-card-container'));
            if (instance) instance.hide();
        })
        .on('click', '.previewButton', (e) => {
            e.stopPropagation();
            fetchDataForHorse($(e.target).closest('.ds-card-container'), mappy);
            $('#dynamic-gallery .previewButton').removeClass('active');
            $('#dynamic-gallery .ds-card-gallery').removeClass('active'); // Remove the active class from all .ds-card-gallery elements
            $(e.target)
                .tooltip('hide')
                .addClass('active')
                .closest('.ds-card-gallery').addClass('active'); // Add the active class to the parent .ds-card-gallery of the clicked .previewButton
        })
        .on('click', '.ds-card-container', function (event) {
            $(event.target).tooltip('hide');
            // Check that the clicked element is not a link within the container
            if ($(event.target).closest('a').length === 0) {
                window.location.href = $(this).data('url');
            }
        });

});