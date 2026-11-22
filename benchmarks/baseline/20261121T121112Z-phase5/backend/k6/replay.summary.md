# k6 summary

scenario: replay

- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_receiving: p(90)=0.171, p(95)=0.202, p(99)=0.335, avg=0.123, min=0.054, med=0.112, max=0.413
- iterations: count=84.000, rate=8.197
- http_req_blocked: p(95)=0.019, p(99)=0.093, avg=0.013, min=0.003, med=0.011, max=0.110, p(90)=0.014
- http_req_sending: avg=0.040, min=0.010, med=0.041, max=0.076, p(90)=0.053, p(95)=0.067, p(99)=0.072
- http_req_duration{expected_response:true}: max=91.764, p(90)=58.304, p(95)=59.498, p(99)=81.716, avg=42.708, min=18.922, med=45.255
- http_req_waiting: max=91.656, p(90)=58.123, p(95)=59.351, p(99)=81.566, avg=42.545, min=18.826, med=45.075
- http_req_duration: avg=42.708, min=18.922, med=45.255, max=91.764, p(90)=58.304, p(95)=59.498, p(99)=81.716
- vus: min=2.000, max=2.000
- http_req_failed: rate=0.000
- http_req_connecting: p(95)=0.000, p(99)=0.070, avg=0.002, min=0.000, med=0.000, max=0.080, p(90)=0.000
