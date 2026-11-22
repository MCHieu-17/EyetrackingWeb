# k6 summary

scenario: outline

- http_req_connecting: avg=0.001, min=0.000, med=0.000, max=0.120, p(90)=0.000, p(95)=0.000, p(99)=0.001
- http_req_receiving: med=0.125, max=0.308, p(90)=0.184, p(95)=0.199, p(99)=0.303, avg=0.122, min=0.027
- iterations: count=100.000, rate=4.774
- vus: min=1.000, max=1.000
- http_req_sending: max=0.076, p(90)=0.051, p(95)=0.054, p(99)=0.065, avg=0.041, min=0.011, med=0.041
- http_req_waiting: med=8.519, max=41.443, p(90)=9.859, p(95)=10.018, p(99)=11.578, avg=8.226, min=1.899
- http_req_failed: rate=0.000
- http_req_blocked: p(95)=0.015, p(99)=0.046, avg=0.012, min=0.003, med=0.011, max=0.166, p(90)=0.013
- http_req_duration{expected_response:true}: max=41.565, p(90)=10.044, p(95)=10.340, p(99)=11.761, avg=8.388, min=1.949, med=8.690
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: p(90)=10.044, p(95)=10.340, p(99)=11.761, avg=8.388, min=1.949, med=8.690, max=41.565
