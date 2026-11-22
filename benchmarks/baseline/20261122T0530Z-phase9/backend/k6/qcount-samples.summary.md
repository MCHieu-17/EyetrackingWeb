# k6 summary

scenario: samples

- http_req_receiving: avg=0.159, min=0.054, med=0.140, max=0.522, p(90)=0.207, p(95)=0.229, p(99)=0.464
- http_req_connecting: avg=0.008, min=0.000, med=0.000, max=0.152, p(90)=0.000, p(95)=0.008, p(99)=0.123
- http_req_duration: p(90)=23.478, p(95)=23.785, p(99)=24.451, avg=18.976, min=7.564, med=22.528, max=24.618
- http_req_duration{expected_response:true}: p(99)=24.451, avg=18.976, min=7.564, med=22.528, max=24.618, p(90)=23.478, p(95)=23.785
- http_req_sending: avg=0.042, min=0.012, med=0.042, max=0.073, p(90)=0.054, p(95)=0.068, p(99)=0.072
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_failed: rate=0.000
- iterations: count=20.000, rate=4.545
- vus: min=1.000, max=1.000
- http_req_blocked: max=0.205, p(90)=0.013, p(95)=0.037, p(99)=0.171, avg=0.020, min=0.003, med=0.011
- http_req_waiting: med=22.348, max=24.043, p(90)=23.285, p(95)=23.493, p(99)=23.933, avg=18.775, min=7.481
