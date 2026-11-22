# k6 summary

scenario: course_students

- http_req_connecting: avg=0.003, min=0.000, med=0.000, max=0.066, p(90)=0.000, p(95)=0.003, p(99)=0.053
- http_req_receiving: avg=0.188, min=0.035, med=0.171, max=0.344, p(90)=0.333, p(95)=0.337, p(99)=0.343
- http_req_duration: med=10.409, max=26.232, p(90)=12.014, p(95)=13.903, p(99)=23.766, avg=10.553, min=2.258
- http_req_waiting: p(90)=11.785, p(95)=13.535, p(99)=23.568, avg=10.319, min=2.179, med=10.081, max=26.076
- http_req_blocked: avg=0.018, min=0.004, med=0.012, max=0.096, p(90)=0.027, p(95)=0.043, p(99)=0.085
- iterations: count=20.000, rate=4.726
- http_req_duration{expected_response:true}: max=26.232, p(90)=12.014, p(95)=13.903, p(99)=23.766, avg=10.553, min=2.258, med=10.409
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- vus: min=1.000, max=1.000
- http_req_sending: med=0.042, max=0.078, p(90)=0.053, p(95)=0.065, p(99)=0.076, avg=0.045, min=0.013
- http_req_failed: rate=0.000
