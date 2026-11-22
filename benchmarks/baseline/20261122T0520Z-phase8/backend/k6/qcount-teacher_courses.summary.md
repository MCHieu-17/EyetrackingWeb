# k6 summary

scenario: teacher_courses

- http_req_failed: rate=0.000
- http_req_duration: med=10.110, max=20.320, p(90)=12.227, p(95)=12.754, p(99)=18.807, avg=8.973, min=2.593
- http_req_blocked: p(95)=0.024, p(99)=0.085, avg=0.015, min=0.003, med=0.011, max=0.100, p(90)=0.020
- http_req_connecting: p(99)=0.057, avg=0.004, min=0.000, med=0.000, max=0.071, p(90)=0.000, p(95)=0.004
- iterations: rate=4.762, count=20.000
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_duration{expected_response:true}: med=10.110, max=20.320, p(90)=12.227, p(95)=12.754, p(99)=18.807, avg=8.973, min=2.593
- http_req_waiting: p(99)=18.699, avg=8.826, min=2.527, med=9.866, max=20.222, p(90)=12.064, p(95)=12.606
- http_req_receiving: p(90)=0.168, p(95)=0.180, p(99)=0.235, avg=0.110, min=0.042, med=0.110, max=0.249
- vus: min=1.000, max=1.000
- http_req_sending: max=0.058, p(90)=0.050, p(95)=0.051, p(99)=0.057, avg=0.038, min=0.012, med=0.041
