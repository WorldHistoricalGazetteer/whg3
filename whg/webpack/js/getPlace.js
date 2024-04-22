import { minmaxer } from './utilities';
import debounce from 'lodash/debounce';

export function popupFeatureHTML(feature, clickable=true) { // TODO: Improve styling with css and content?
	let HTML = '<b>' + feature.properties.title + '</b><br/>' +
    'Temporality: ' + (feature.properties.min ? feature.properties.min : '?') + '/' + (feature.properties.max ? feature.properties.max : '?') + 
    (clickable ? '<br/>Click to focus' : '');
    return (HTML);
}

export const getPlace = debounce(getPlaceBouncing, 300);
export function getPlaceBouncing(pid, cid, spinner_detail, callback) {
    const cidQueryParam = Number.isInteger(cid) ? `?cid=${cid}` : '';
    $.ajax({
        url: `/api/place/${pid}${cidQueryParam}`,
    }).done(handlePlaceData);		

	function handlePlaceData(data) {
	    if (cidQueryParam=='') {
	        $("#detail").html(parsePlace(data));
	    } else {
	        window.payload = data;
	        $("#anno_title").html('<b>' + data.title + '</b>');
	        //console.log('img', data.traces.image_file);
	        $("#anno_body").html(parseAnno(data.traces));
	        $("#anno_img").html(data.traces.image_file);
	    }
	    if (spinner_detail) spinner_detail.stop()
	
	    if (typeof callback === 'function') {
	        callback(data);
	    }
	}
}

function parsePlace(data) {
	window.featdata = data
	var descrip = '';
	// DATASETS
	if (!!data.datasets && data.datasets.length > 0) {
		const dataset_links = data.datasets.map(ds => `<a href="/datasets/${ds.id}/places" target="_blank" data-bs-toggle="tooltip" data-bs-title="View <i>${ds.title}</i> in a new tab.">${ds.title} <i class="fas fa-external-link-alt linky"></i></a>`).join('; ')
		descrip += `<p class="mb-0"><b>Dataset${data.datasets.length == 1 ? '' : 's'}</b>: ${dataset_links}.</p>`;
	}
	//
	// NAME VARIANTS
	if (!!data.names && data.names.length > 0) {
	    const nameVariants = data.names
		    .filter(name => !!name.toponym && name.toponym.trim() !== '')
	    	.map(name => {
	        let nameHtml = name.toponym;
	        if (name.citations && name.citations.length > 0) {
	            const citation = name.citations[0]; // Assuming only one citation is considered
	            const label = citation.label || '';
	            const id = citation.id || '';
	            if (id !== '' && label !== '') {
	                // If both id and label exist, wrap the name in a link with tooltip
	                nameHtml = `<a href="${id}" target="_blank" data-bs-toggle="tooltip" title="${label}">${nameHtml} <i class="fas fa-external-link-alt linky"></i></a>`;
	            } else {
	                // If only label exists, show tooltip without link
	                nameHtml = `<span data-bs-toggle="tooltip" title="${label}" class="pointer">${nameHtml}</span>`;
	            }
	        }
	        return nameHtml;
	    	})
	    	.join('; ');
	
	    if (nameVariants !== '') descrip += `<p class="scroll65"><b>Variant${data.names.length == 1 ? '' : 's'}</b>: ${nameVariants}.</p>`;
	}
	//
	// TYPES
	// may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
	if (!!data.types && data.types.length > 0) {
	    const types = data.types
		    .filter(type => !!type.label && type.label.trim() !== '')
		    .map(type => {
		        const sourceLabels = type.sourceLabel || type.sourceLabels.map(sourceLabel => sourceLabel.label).join(' | ');
		        return `<${!!type.url ? `a href="${type.url}" target="_blank"` : `span`} data-bs-toggle="tooltip" title="<b>${type.identifier}</b><p>${sourceLabels}</p>">${type.label}${!!type.url ? ` <i class="fas fa-external-link-alt linky"></i>` : ``}</${!!type.url ? `a` : `span`}>`;
		    })
		    .join('; ');
	    if (types !== '') descrip += `<p class="mb-0"><b>Type${data.types.length == 1 ? '' : 's'}</b>: ${types}.</p>`;
	}
	
	function build_links(name, links_array, link_text=false) {
		if (links_array.length == 0) return '';
		const links = links_array
			.map(link => {
				const timespan = (!!link.when && !!link.when.timespans) 
				    ? ` (${minmaxer(link.when.timespans)})` 
				    : (!!link.when && !link.when.timespans) 
				    ? ` (${link.when.start.in}-${link.when.end.in})` 
				    : '';
	        	return `${link_text ? `${link.value}${!!link.url ? ' ' : ''}` : ''}
	        			${link_text && !link.url ? '' : `
		        			<${!!link.url ? `a href="${link.url}" target="_blank"` : `span`}${link_text ? ' class="pointer small red-bold"' : ''}>
		        				${link_text || link.identifier || link.label}${timespan}${!!link.url ? ` <i class="fas fa-external-link-alt linky"></i>` : ``}
		        			</${!!link.url ? `a` : `span`}>
	        			`}
	        			`;
		    })
		    .join('; ');
		return links == '' ? '' : `<p class="mb-0"><b>${name}${links_array.length == 1 || name == 'Related' ? '' : 's'}</b>: ${links}</p>`;
	}
	//
	// LINKS
	//
	if (!!data.links && data.links.length > 0) {
	    descrip += build_links('Link', data.links.filter(link => !!link.identifier && link.identifier.trim() !== ''));	    
	}
	//
	// RELATED
	//
	if (!!data.related && data.related.length > 0) {
	    descrip += build_links('Parent', data.related.filter(relative => !!relative.relation_type && relative.relation_type == 'gvp:broaderPartitive'));
	    descrip += build_links('Related', data.related.filter(relative => !!relative.relation_type && relative.relation_type !== 'gvp:broaderPartitive'));
	}
	//
	// DESCRIPTIONS
	//
	if (!!data.descriptions && data.descriptions.length > 0) {
	    descrip += build_links('Description', data.descriptions.filter(link => !!link.value && link.value.trim() !== ''), 'Link');	    
	}
	//
	// CCODES
	//
	if (!!data.countries && data.countries.length > 0) {
	    descrip += '<p><b>Modern country bounds</b>: ' + data.countries.map(country => `<span class="pointer" data-bs-toggle="tooltip" title="${country.label || ''}">${country.ccode}</span>`).join(', ') + '</p>';
	}
	//
	// MINMAX
	//
	if (!!data.minmax && data.minmax.length == 2 && (data.minmax[0] || data.minmax[1]) ) {
		descrip += `<p><b>When</b>: earliest: ${data.minmax[0] ? data.minmax[0] : '?'}; latest: ${data.minmax[1] ? data.minmax[1] : '?'}</p>`;
	}	
	//
	// TITLE
	//
	descrip = `<div><p><b>Title</b>: <span id="row_title" class="larger text-danger">${data.title}</span></p>${descrip}</div>`;
	
	return descrip
}

// Traces (annotations)
function parseAnno(data) {
	let descrip = ''
	if (data.length > 0) {
		// there is *always* a trace, even if not saved
		// TODO: no need to find/filter here? done in view?
		let trace = data.find(function(d) {
			return d.fields.collection == `${ pageData }`
		})
		let t = trace.fields
		let imgpath = t.image_file
		let blank = t.relation == '[""]' && t.note == null && t.start == null
		if (blank) {
			descrip += '<i>none yet</i>'
		} else {
			if (t.relation) {
				descrip += "<span><b><u>Relation</u></b>: " +
					JSON.parse(t.relation)[0] + "</span>"
			}
			if (t.note) {
				// find & format embedded markdown link syntax
				let linkish = t.note.replace(/\[(.*)\]\((.*)\)/gim,
					'<a href="$2" target="_blank">$1</a>')
				// index of link, -1 is none
				let linkindex = linkish.search(/<a href/gim)
				if (linkindex == -1) {
					// no links, truncate if > 250 chars
					descrip += '<p><b><u>Notes</u></b>: ' +
						readMore(linkish, 250) + '</p>'
				} else {
					// TODO: Nothing appears to be happening with this variable?
					// has a link, get initial text
					let text = linkish.slice(0, linkindex)
					let innerlink = linkish.slice(linkindex, )
					descrip += '<p><b><u>Notes</u></b>: ' +
						readMore(text, 250, innerlink) + '</p>'
				}
			}
			if (t.start) {
				descrip += '<p><b><u>Begin/End</u></b>: ' + (t.start ?? "") + '/' +
					(t.end ?? '') + '</p>'
			}
		}
		if (imgpath != "") {
			// display annotation image if any
			$("#anno_img").attr('src', '/media/' + imgpath)
		} else {
			// trace has no image
			$("#active_img").attr('src', `/media/${ window.collimagepath }`)
		}
	} else {
		console.log('no trace for selected place')
		// restore collection image if others have been viewed
		$("#active_img").attr('src', `/media/${ window.collimagepath }`)
	}
	return descrip
}

// TODO: this is a mess, refactor or add 1-to-many annotation link field
// truncate anno note, looking for embedded links
function readMore(text, numchars, innerlink = '') {
	let dots = '<span id="dots">...</span>'
	let link = '<a href="#" class="a_more" onclick="showMore()">more</a><span class="more hidden">'
	if (text.length < numchars) {
		return innerlink != '' ? text + innerlink : text
	} else {
		return text.slice(0, numchars) + dots + link + text.slice(numchars, ) + innerlink +
			' <a href="#" class="ms-2 a_less hidden" onclick="showLess()">less</a></span>'
	}
}
