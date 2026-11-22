# k6 summary

scenario: aoi_summary

- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: p(99)=45.142, avg=29.770, min=10.055, med=33.603, max=46.512, p(90)=36.507, p(95)=39.659
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- iterations: count=20.000, rate=4.331
- http_req_connecting: med=0.000, max=0.076, p(90)=0.000, p(95)=0.004, p(99)=0.061, avg=0.004, min=0.000
- http_req_duration: max=46.512, p(90)=36.507, p(95)=39.659, p(99)=45.142, avg=29.770, min=10.055, med=33.603
- http_req_blocked: p(95)=0.021, p(99)=0.090, avg=0.016, min=0.004, med=0.011, max=0.107, p(90)=0.014
- http_req_sending: max=0.099, p(90)=0.064, p(95)=0.082, p(99)=0.096, avg=0.053, min=0.016, med=0.051
- vus: min=1.000, max=1.000
- http_req_waiting: avg=29.625, min=9.923, med=33.494, max=46.327, p(90)=36.365, p(95)=39.444, p(99)=44.950
- http_req_receiving: max=0.219, p(90)=0.136, p(95)=0.161, p(99)=0.207, avg=0.092, min=0.051, med=0.077
