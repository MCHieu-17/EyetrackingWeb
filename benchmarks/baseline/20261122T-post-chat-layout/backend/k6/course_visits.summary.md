# k6 summary

scenario: course_visits

- http_req_duration{expected_response:true}: p(90)=13.434, p(95)=14.374, p(99)=17.847, avg=8.793, min=1.906, med=8.185, max=23.689
- http_req_sending: max=0.780, p(90)=0.050, p(95)=0.058, p(99)=0.123, avg=0.045, min=0.005, med=0.041
- http_req_receiving: p(99)=0.535, avg=0.150, min=0.018, med=0.121, max=0.881, p(90)=0.313, p(95)=0.374
- http_req_blocked: avg=0.014, min=0.002, med=0.011, max=0.153, p(90)=0.014, p(95)=0.017, p(99)=0.134
- iterations: count=240.000, rate=23.649
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_duration: avg=8.793, min=1.906, med=8.185, max=23.689, p(90)=13.434, p(95)=14.374, p(99)=17.847
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.103, p(90)=0.000, p(95)=0.000, p(99)=0.101
- http_req_waiting: avg=8.598, min=1.842, med=8.006, max=23.597, p(90)=13.209, p(95)=13.915, p(99)=17.565
