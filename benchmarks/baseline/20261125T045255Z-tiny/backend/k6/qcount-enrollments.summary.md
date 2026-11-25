# k6 summary

scenario: enrollments

- iterations: count=20.000, rate=4.873
- vus: max=1.000, min=1.000
- http_req_receiving: avg=0.123, min=0.037, med=0.119, max=0.260, p(90)=0.169, p(95)=0.175, p(99)=0.243
- http_req_duration: avg=4.155, min=1.140, med=4.365, max=4.643, p(90)=4.536, p(95)=4.620, p(99)=4.638
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_sending: avg=0.043, min=0.014, med=0.042, max=0.060, p(90)=0.053, p(95)=0.054, p(99)=0.059
- http_req_duration{expected_response:true}: p(99)=4.638, avg=4.155, min=1.140, med=4.365, max=4.643, p(90)=4.536, p(95)=4.620
- http_req_waiting: avg=3.989, min=1.088, med=4.156, max=4.473, p(90)=4.386, p(95)=4.470, p(99)=4.472
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.072, p(90)=0.000, p(95)=0.004, p(99)=0.059
- http_req_blocked: avg=0.016, min=0.004, med=0.011, max=0.107, p(90)=0.016, p(95)=0.022, p(99)=0.090
- http_req_failed: rate=0.000
