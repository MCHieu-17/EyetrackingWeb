# k6 summary

scenario: add_students

- http_req_waiting: avg=9.904, min=3.456, med=8.667, max=17.189, p(90)=17.037, p(95)=17.113, p(99)=17.174
- http_req_blocked: min=0.004, med=0.010, max=0.101, p(90)=0.022, p(95)=0.061, p(99)=0.093, avg=0.018
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_sending: avg=0.051, min=0.018, med=0.050, max=0.107, p(90)=0.069, p(95)=0.088, p(99)=0.103
- http_req_duration: p(90)=17.140, p(95)=17.243, p(99)=17.325, avg=10.033, min=3.506, med=8.769, max=17.345
- http_req_receiving: avg=0.079, min=0.030, med=0.045, max=0.199, p(90)=0.195, p(95)=0.197, p(99)=0.199
- http_req_failed: rate=0.000
- iterations: count=10.000, rate=4.738
- http_req_connecting: min=0.000, med=0.000, max=0.074, p(90)=0.007, p(95)=0.041, p(99)=0.067, avg=0.007
- http_req_duration{expected_response:true}: max=17.345, p(90)=17.140, p(95)=17.243, p(99)=17.325, avg=10.033, min=3.506, med=8.769
- vus: min=1.000, max=1.000
