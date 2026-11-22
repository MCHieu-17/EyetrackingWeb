# k6 summary

scenario: course_visits

- http_req_sending: avg=0.042, min=0.012, med=0.043, max=0.076, p(90)=0.047, p(95)=0.052, p(99)=0.071
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_receiving: p(99)=1.616, avg=0.376, min=0.048, med=0.353, max=1.864, p(90)=0.523, p(95)=0.626
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.092, p(90)=0.000, p(95)=0.005, p(99)=0.075
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_duration: p(99)=16.418, avg=10.996, min=3.134, med=11.888, max=16.605, p(90)=15.369, p(95)=15.668
- iterations: count=20.000, rate=4.716
- http_req_duration{expected_response:true}: p(90)=15.369, p(95)=15.668, p(99)=16.418, avg=10.996, min=3.134, med=11.888, max=16.605
- http_req_blocked: med=0.012, max=0.131, p(90)=0.014, p(95)=0.021, p(99)=0.109, avg=0.017, min=0.004
- http_req_waiting: p(90)=14.720, p(95)=14.918, p(99)=15.063, avg=10.578, min=3.017, med=11.349, max=15.099
