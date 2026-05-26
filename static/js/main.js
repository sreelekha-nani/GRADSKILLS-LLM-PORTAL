// Video progress tracking webhook
function trackVideoProgress(videoId, courseId, progressPercent) {
    fetch('/webhook/video_progress', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            video_id: videoId,
            course_id: courseId,
            progress: progressPercent
        })
    })
    .then(response => response.json())
    .then(data => console.log('Progress updated', data))
    .catch(error => console.error('Error tracking progress:', error));
}

// Generate certificate webhook
function generateCertificate(courseId) {
    const btn = document.getElementById('cert-btn');
    btn.disabled = true;
    btn.innerText = 'Generating...';
    
    fetch('/webhook/generate_certificate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            course_id: courseId
        })
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'success') {
            window.location.href = data.url;
            btn.innerText = 'Certificate Downloaded';
        } else {
            alert('Error generating certificate');
            btn.disabled = false;
            btn.innerText = 'Download Certificate';
        }
    })
    .catch(error => {
        console.error('Error:', error);
        btn.disabled = false;
        btn.innerText = 'Download Certificate';
    });
}
