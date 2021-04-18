function load(path) {
    const main = document.getElementsByTagName('main')[0];
    main.textContent = 'Loading...';

    const setErr = function(msg) {
        main.innerHTML = '';
        const err = document.createElement('div');
        err.classList.add('error')
        err.textContent = msg;
        main.append(err);
    };

    const addCollapsor = function() {
        const collapsor = document.createElement('a');
        collapsor.classList.add('collapse');
        collapsor.href = '';
        collapsor.textContent = '[-]';
        collapsor.addEventListener('click', e => {
            e.preventDefault();
            const contents = e.target.parentElement.parentElement.children;
            const collapse = e.target.textContent == '[-]';
            for (let i = 0; i < contents.length; i++) {
                if (i > 0) {
                    contents[i].hidden = collapse;
                }
            }
            e.target.textContent = collapse ? '[+]' : '[-]';
        });
        return collapsor;
    };

    const setFilter = function(status, value) {
        for (const row of document.querySelectorAll('.edit tr')) {
            const cell = row.querySelector('.line-status');
            if (cell !== null && cell.textContent == status) {
                row.hidden = !value;
            }
        }
    };

    const colors = {};
    const makeColor = function(val) {
        if (colors[val] !== undefined) {
            return colors[val];
        }
        let hash = 0;
        for (let i = 0; i < val.length; i++) {
            hash = ((hash << 5) - hash) + val.charCodeAt(i);
        }
        hash = hash & hash;
        colors[val] = `hsla(${hash % 360}, 70%, 70%, 0.3)`;
        return colors[val];
    }

    const renderEdits = function(edits) {
        const toc = document.createElement('ul');
        const tocItemTmpl = document.getElementById('toc-item-tmpl');
        const optionsTmpl = document.getElementById('options-tmpl');
        const sectionTmpl = document.getElementById('section-tmpl');
        const pageTmpl = document.getElementById('page-tmpl');
        const editTmpl = document.getElementById('edit-tmpl');
        const lineTmpl = document.getElementById('line-tmpl');

        toc.classList.add('toc');
        main.innerHTML = '';
        main.append(toc);

        main.append(optionsTmpl.content.cloneNode(true));

        let curSecName = null, curSecElem = null, sectionCtr = 1;
        let curPageName = null, curPageElem = null;

        edits.forEach(edit => {
            if (curSecName !== edit.section) {
                curSecElem = sectionTmpl.content.cloneNode(true).children[0];
                const head = curSecElem.querySelector('h2');
                head.id = `section-${sectionCtr}`;
                head.textContent = edit.section;
                head.prepend(addCollapsor());
                main.append(curSecElem);
                curSecName = edit.section;
                sectionCtr++;

                const li = tocItemTmpl.content.cloneNode(true).children[0];
                li.querySelector('a').href = `#section-${sectionCtr}`;
                li.querySelector('a').textContent = edit.section;
                toc.append(li);
            }

            if (curPageName !== edit.page) {
                curPageElem = pageTmpl.content.cloneNode(true).children[0];
                curPageElem.querySelector('a').href += edit.page.replaceAll(' ', '_');
                curPageElem.querySelector('a').textContent = edit.page;
                curPageElem.querySelector('h3').prepend(addCollapsor());
                curSecElem.append(curPageElem);
                curPageName = edit.page;
            }

            const item = editTmpl.content.cloneNode(true).children[0];
            item.querySelector('h4 a').href += edit.diff;
            item.querySelector('h4 a').textContent = edit.diff;
            item.querySelector('h4').prepend(addCollapsor());

            const table = item.querySelector('table');
            edit.delta.lines.forEach(line => {
                const row = lineTmpl.content.cloneNode(true).children[0];
                row.querySelector('.line-index').textContent = line.index;
                const lineStatus = row.querySelector('.line-status');
                lineStatus.textContent = line.culled ? 'autocull' : 'live';
                lineStatus.classList.add(lineStatus.textContent);
                row.querySelector('.line-text').textContent = line.text;
                row.querySelector('.line-text').classList.add(lineStatus.textContent);
                line.rules.forEach(rule => {
                    let it;
                    if (rule.detail) {
                        it = document.createElement('abbr');
                        it.title = rule.detail;
                    } else {
                        it = document.createElement('span');
                    }
                    it.textContent = rule.name;
                    it.style.backgroundColor = makeColor(rule.name);
                    row.querySelector('.line-rules').append(it);
                });
                table.append(row);
            });
            curPageElem.append(item);
        });

        document.getElementById('show-culled').addEventListener('change', e => {
            setFilter('autocull', e.currentTarget.checked);
        });
        document.getElementById('show-live').addEventListener('change', e => {
            setFilter('live', e.currentTarget.checked);
        });

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('culled') === '0') {
            document.getElementById('show-culled').checked = false;
            setFilter('autocull', false);
        }
        if (urlParams.get('live') === '0') {
            document.getElementById('show-live').checked = false;
            setFilter('live', false);
        }
    };

    fetch(path).then(resp => {
        if (!resp.ok) {
            console.log('Error fetching diffs', resp);
            setErr(`Could not load diffs! Error ${resp.status}`);
            return;
        }
        return resp.arrayBuffer();
    }).then(buff => {
        let raw, edits;
        const compressed = new Uint8Array(buff);
        try {
            raw = pako.inflate(compressed, {to: 'string'});
        } catch (err) {
            setErr(`Could not decompress diffs! ${err}`);
            return;
        }
        try {
            edits = JSON.parse(raw);
        } catch (err) {
            setErr(`Could not parse diffs! ${err}`);
            return;
        }
        renderEdits(edits);
    });
}
