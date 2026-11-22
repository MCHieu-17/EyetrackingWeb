# k6 summary

scenario: add_students

- iterations: count=10.000, rate=4.445
- http_req_waiting: p(95)=29.025, p(99)=29.344, avg=23.180, min=12.718, med=26.359, max=29.423, p(90)=28.627
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: p(95)=29.263, p(99)=29.568, avg=23.447, min=12.964, med=26.619, max=29.644, p(90)=28.882
- http_req_failed: rate=0.000
- http_req_duration: avg=23.447, min=12.964, med=26.619, max=29.644, p(90)=28.882, p(95)=29.263, p(99)=29.568
- http_req_blocked: min=0.010, med=0.011, max=0.117, p(90)=0.023, p(95)=0.070, p(99)=0.108, avg=0.022
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_connecting: max=0.084, p(90)=0.008, p(95)=0.046, p(99)=0.076, avg=0.008, min=0.000, med=0.000
- http_req_receiving: p(99)=0.230, avg=0.064, min=0.026, med=0.037, max=0.242, p(90)=0.119, p(95)=0.181
- http_req_sending: p(95)=0.236, p(99)=0.243, avg=0.203, min=0.094, med=0.219, max=0.245, p(90)=0.226
