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
	//console.log('getPlace()', pid);
	if (isNaN(pid)) {
		console.log('Invalid pid');
		return;
	}
	const cidQueryParam = Number.isInteger(cid) ? `?cid=${cid}` : '';
	$.ajax({
		url: `/api/place/${pid}${cidQueryParam}`,
	}).done(function(data) {
		if (cidQueryParam == '') {
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
		
		// events on detail items
		$('.ext').on('click', function(e) {
			e.preventDefault();
			let str = $(this).text();
			let url; // Must be scoped outwith if/else
			//console.log('str (identifier)',str)-->
			// URL identifiers can be 'http*' or an authority prefix
			if (str.substring(0, 4).toLowerCase() == 'http') {
				url = str;
			} else {
				var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
				const matches = str.match(re);
				url = base_urls[matches[1]] + matches[2];
				console.log(base_urls,matches,'url', url)
			}
			window.open(url, '_blank');
		});
		$('.exttab').on('click', function(e) {
			e.preventDefault();
			let id = $(this).data('id')
			//console.log('id', id)
			var re = /(http|dbp|gn|tgn|wd|loc|viaf|aat):(.*?)$/;
			let url = id.match(re)[1] == 'http' ? id : base_urls[id.match(re)[1]] + id.match(re)[2]
			//console.log('url', url)
			window.open(url, '_blank')
		});
	});
	//spinner_detail.stop()-->
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

// Single place
function parsePlace(data) { // TODO: See also commented code at bottom
	window.featdata = data

	function onlyUnique(array) {
		const map = new Map();
		const result = [];
		for (const item of array) {
			if (!map.has(item.identifier)) {
				map.set(item.identifier, true);
				result.push({
					identifier: item.identifier,
					type: item.type,
					aug: item.aug
				});
			}
		}
		return (result)
	}
	//timespan_arr = []-->
	//
	// TITLE
	var descrip = '<p><b>Title</b>: <span id="row_title" class="larger text-danger">' + data.title + '</span>'
	//
	// NAME VARIANTS
	descrip += '<p class="scroll65"><b>Variants</b>: '
	console.log('data.names', data.names)
	for (var n in data.names) {
		let name = data.names[n]
		descrip += '<p>' + name.toponym != '' ? name.toponym + '; ' : ''
	}
	//
	// TYPES
	// may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
	// console.log('data.types',data.types)
	//{"label":"","identifier":"aat:___","sourceLabels":[{"label":" ","lang":"en"}]}
	if(data.types.length > 0) {
		descrip += '</p><p><b>Types</b>: '
		var typeids = ''
		for (var t in data.types) {
			var str = ''
			var type = data.types[t]
			if ('sourceLabels' in type) {
				let srclabels = type.sourceLabels
				for (let l in srclabels) {
					let label = srclabels[l]['label']
					str = label != '' ? label + '; ' : ''
				}
			} else if ('sourceLabel' in type) {
				str = type.sourceLabel != '' ? type.sourceLabel + '; ' : ''
			}
			if (type.label != '') {
				str += url_exttype(type) + ' '
			}
			typeids += str
		}
		descrip += typeids.replace(/(; $)/g, "") + '</p>'
	}
	//
	// LINKS
	//
	descrip += '<p class="mb-0"><b>Links</b>: '
	//close_count = added_count = related_count = 0
	var html = ''
	if (data.links.length > 0) {
		let links = data.links
		let links_arr = onlyUnique(data.links)
		/*console.log('distinct data.links',links_arr)*/
		for (var l in links_arr) {
			descrip += url_extplace(links_arr[l].identifier)
		}
	} else {
		descrip += "<i class='small'>no links established yet</i>"
	}
	descrip += '</p>'

	//
	// RELATED
	//right=''-->
	if (data.related.length > 0) {
		let parent = '<p class="mb-0"><b>Parent(s)</b>: ';
		let related = '<p class="mb-0"><b>Related</b>: ';
		for (var r in data.related) {
			const rel = data.related[r]
			//console.log('rel',rel)-->
			if (rel.relation_type == 'gvp:broaderPartitive') {
				parent += '<span class="small h1em">' + rel.label
				parent += 'when' in rel && !('timespans' in rel.when) ?
					', ' + rel.when.start.in + '-' + rel.when.end.in :
					'when' in rel && ('timespans' in rel.when) ? ', ' +
					minmaxer(rel.when.timespans) : ''
				//rel.when.timespans : ''-->
				parent += '</span>; '
			} else {
				related += '<p class="small h1em">' + rel.label + ', ' + rel.when.start.in + '-' + rel.when.end.in + '</p>'
			}
		}
		descrip += parent.length > 39 ? parent : ''
		descrip += related.length > 37 ? related : ''
	}
	//
	// DESCRIPTIONS
	// TODO: link description to identifier URI if present
	if (data.descriptions.length > 0) {
		let val = data.descriptions[0]['value'].substring(0, 300)
		descrip += '<p><b>Description</b>: ' + (val.startsWith('http') ? '<a href="' + val + '" target="_blank">Link</a>' : val) +
			' ... </p>'
		//'<br/><span class="small red-bold">('+data.descriptions[0]['identifier']+')</span>-->
	}
	//
	// CCODES
	//
	//if (data.ccodes.length > 0) {-->
	if (!!data.countries) {
		//console.log('data.countries',data.countries)-->
		descrip += '<p><b>Modern country bounds</b>: ' + data.countries.join(', ') + '</p>'
	}
	//
	// MINMAX
	//
	if (data.minmax && data.minmax.length > 0) {
		descrip += '<p><b>When</b>: earliest: ' + data.minmax[0] + '; latest: ' + data.minmax[1]
	}
	descrip += '</div>'
	return descrip
}

// builds link for external place record
function url_extplace(identifier) {
	var link = ''
	// abbreviate links not in aliases.base_urls
	if (identifier.startsWith('http')) {
		const tag = identifier.replace(/.+\/\/|www.|\..+/g, '')
		link = '<a href="' + identifier + '" target="_blank">' + tag + '<i class="fas fa-external-link-alt linky"></i>,  </a>';
	} else {
		link = '<a href="" class="ext" data-target="#ext_site">' + identifier + '&nbsp;<i class="fas fa-external-link-alt linky"></i></a>, ';
	}
	return link;
}

// builds link for external placetype record
function url_exttype(type) {
	let link = ' <a href="#" class="exttab" data-id=' + type.identifier +
		'>(' + type.label + ' <i class="fas fa-external-link-alt linky"></i>)</a>'
	return link
}

function showMore() {
	let clicked = $(this)
	$(".more").show()
	console.log('clicked $this', clicked)
	$(".a_more").hide()
	$("#dots").hide()
	clicked.next().show()
	$(".a_less").show()
}

function showLess() {
	let clicked = $(this)
	console.log('clicked less', clicked)
	clicked.hide() // hide 'less' link
	$(".more").hide() // hide the extra text again
	$("#dots").show() // show dots again
	$(".a_more").show() // show more link again
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

/*

THIS VERSION OF parsePlace is more developed, but not actually used where it was found, in places_collection_browse


//
function toggleLinks() {
    label = $("#togglelinks").text()
        $("#togglelinks").text(label == 'Show' ? 'Hide' : 'Show');
    $('#p_links').toggle()
}
function toggleNames() {
    label = $("#togglenames").text()
        $("#togglenames").text(label == 'More' ? 'Less' : 'More');
    $('#s_names').toggle()
}


// SINGLE PLACE
function parsePlace(data) {
    window.featdata = data

    function onlyUnique(array) {
        const map = new Map();
        const result = [];
        for (const item of array) {
            if (!map.has(item.identifier)) {
                map.set(item.identifier, true);
                result.push({
                    identifier: item.identifier,
                    type: item.type,
                    aug: item.aug
                });
            }
        }
        return (result)
    }

    //
    // NAME VARIANTS
    // display first 5
    descrip = '<p class="scroll100"><b><u>Name variants</u></b>: '
        for (n in data.names.slice(0, 5)) {
            let name = data.names[n]
                descrip += name.toponym != '' ? name.toponym + '; ' : ''
        }
        // if > 5 add link and toggle-able span
        if (data.names.length > 5) {
            descrip += ' <a href="#" onclick="toggleNames()" id="togglenames">More</a> <span id="s_names" class="mb-0 hidden">'
            for (n in data.names.slice(6, )) {
                let name = data.names[n]
                    descrip += name.toponym != '' ? name.toponym + '; ' : ''
            }
            descrip += '</span>'
        }
        descrip += '</p>'
        //
        // TYPES
        // may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
        // console.log('data.types',data.types)
        if (data.types && data.types.length > 0) {
            descrip += '</p><p><b><u>Place type</u></b>: '
            typeids = ''
                for (t in data.types) {
                    str = ''
                        var type = data.types[t]
                        if ('sourceLabels' in type) {
                            srclabels = type.sourceLabels
                                for (l in srclabels) {
                                    label = srclabels[l]['label']
                                        str = label != '' ? label + '; ' : ''
                                }
                        } else if ('sourceLabel' in type) {
                            str = type.sourceLabel != '' ? type.sourceLabel + '; ' : ''
                        }
                        typeids += str
                }
                descrip += typeids.replace(/(; $)/g, "") + '</p>'
        }
        //
        // MINMAX
        //
        if (data.minmax && data.minmax[0]) {
            descrip += '<p><b><u>When</u></b>: earliest: ' + data.minmax[0] +
            (data.minmax[1] ? '; latest: ' + data.minmax[1] : '')
        }
        //
        // LINKS
        //
        if (data.links.length > 0) {
            descrip += '<p class="mb-0"><b><u>External links</u> (' + data.links.length + ') </b>' +
            '<a href="#" onclick="toggleLinks()" id="togglelinks">Show</a>'
            descrip += '<br/><span id="p_links" class="hidden">'
            close_count = added_count = related_count = 0
                html = ''
                links = data.links
                links_arr = onlyUnique(data.links)
                for (l in links_arr) {
                    descrip += url_extplace(links_arr[l].identifier)
                }
                descrip += '</span>'
        }
        descrip += '</p>'

        //
        // RELATED
        if (data.related.length > 0) {
            // TODO: this needs better logic; so far only relations are parents but LPF allows for others
            parent = '<p class="mb-0"><b><u>Parent(s)</u></b>: ';
            //
            for (r in data.related) {
                rel = data.related[r]
                    if (rel.relation_type == 'gvp:broaderPartitive') {
                        parent += '<span class="small h1em">' + rel.label
                        parent += 'when' in rel && !('timespans' in rel.when) ?
                        ', ' + rel.when.start.in + '-' + rel.when.end.in :
                        'when' in rel && ('timespans' in rel.when) ? ', ' +
                        minmaxer(rel.when.timespans) : ''
                        parent += '</span>; '
                    } else {
                        related += '<p class="small h1em">' + rel.label + ', ' + rel.when.start.in + '-' + rel.when.end.in + '</p>'
                    }
            }

            descrip += parent.length > 39 ? parent : ''
        }

        //
        // DESCRIPTIONS
        // TODO: link description to identifier URI if present
        if (data.descriptions.length > 0) {
            val = data.descriptions[0]['value'].substring(0, 300)
                descrip += '<p><b><u>Description</u></b>: ' + (val.startsWith('http') ? '<a href="' + val + '" target="_blank">Link</a>' : val)
                 + ' ... </p>'
        }
        //
        // CCODES
        //
        if (!!data.countries) {
            // console.log('data.countries',data.countries)
            descrip += '<p><b><u>Modern country</u></b>: ' + data.countries.join(', ') + '</p>'
        }
        descrip += '</div>'
        //

        return descrip
}

*/
