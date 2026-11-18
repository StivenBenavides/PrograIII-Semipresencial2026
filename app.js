document.addEventListener("DOMContentLoaded", events=>{
    mnxImpuestos.addEventListener('click',e=>{
        e.preventDefault();
        let form = e.target.dataset.form;
        cargarForm(form);
    });
});
function cargarForm(form, callback){
    if( $(`#${form} > form`).length<=0 ){
        fetch(`/vistas?form=${form}`)
        .then(response => response.text())
        .then(ventana => {
            $(`#${form}`).html(ventana).draggable();
            cerrarVentana();
            if(callback) callback();
        })
        .catch(error => console.error('Error al cargar el formulario:', error));
    }else{
        $(`#${form}`).show();
    }
}
function cerrarVentana(){
    $('.btn-close').off('click').on('click',e=>{
        e.preventDefault();
        let form = e.target.dataset.form;
        $(`#${form}`).hide();
    });
}