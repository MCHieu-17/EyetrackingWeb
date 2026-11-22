# k6 summary

scenario: replay

- http_req_blocked: avg=0.022, min=0.007, med=0.011, max=0.162, p(90)=0.041, p(95)=0.065, p(99)=0.142
- http_req_duration: min=5.646, med=16.597, max=19.312, p(90)=19.036, p(95)=19.224, p(99)=19.294, avg=14.793
- vus: min=1.000, max=1.000
- iterations: count=20.000, rate=4.630
- http_req_receiving: med=0.270, max=0.743, p(90)=0.316, p(95)=0.345, p(99)=0.664, avg=0.251, min=0.066
- http_req_failed: rate=0.000
- http_req_connecting: p(95)=0.006, p(99)=0.098, avg=0.006, min=0.000, med=0.000, max=0.121, p(90)=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: avg=14.490, min=5.503, med=16.285, max=18.998, p(90)=18.700, p(95)=18.957, p(99)=18.990
- http_req_duration{expected_response:true}: p(90)=19.036, p(95)=19.224, p(99)=19.294, avg=14.793, min=5.646, med=16.597, max=19.312
- http_req_sending: max=0.156, p(90)=0.062, p(95)=0.076, p(99)=0.140, avg=0.052, min=0.035, med=0.044
