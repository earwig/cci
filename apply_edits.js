$('#firstHeading').append($('<input>', {
    type: 'file',
    id: 'upload-edit',
    multiple: true,
    style: 'margin-left: 1em;',
}));

$('#upload-edit').change(function() {
    for (const file of this.files) {
        const reader = new FileReader();
        reader.addEventListener('load', event => {
            const edit = JSON.parse(event.target.result);
            if (!edit.title || !edit.content || !edit.summary || !edit.revid) {
                return;
            }
            new mw.Api().postWithEditToken({
                action: 'edit',
                title: edit.title,
                text: edit.content,
                summary: edit.summary,
                formatversion: '2',
                baserevid: edit.revid,
                nocreate: true,
                assert: 'user',
            }).done(() => {
                mw.notify(`Edit to [[${edit.title}]] saved`);
            }).fail((code, result) => {
                mw.log.error('Error while saving:', result);
                mw.notify(`Couldn't save [[${edit.title}]]`);
            });
        });
        reader.readAsText(file);
    }
});
